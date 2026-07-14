"""Tests for Shelley staking: certificates, derived views, and rollback."""

from chainidx.model import (
    AccountState,
    Block,
    PoolRegistration,
    PoolRetirement,
    StakeDelegation,
    StakeDeregistration,
    StakeRegistration,
    Tx,
)
from chainidx.store import SqliteStore


def blk(block_no: int, block_hash: str, prev_hash: str, txs: tuple[Tx, ...]) -> Block:
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=txs,
    )


def test_pool_summaries_and_detail() -> None:
    store = SqliteStore()
    certs = (
        PoolRegistration("pool1", 1_000_000, 0.03, "stake_r"),
        StakeRegistration("stake_a"),
        StakeDelegation("stake_a", "pool1"),
    )
    store.apply_block(
        Block(1, 10, "b1", "genesis", txs=(Tx("tx1", certificates=certs),), issuer="pool1")
    )
    store.apply_block(Block(2, 20, "b2", "b1", txs=(), issuer="pool1"))

    summaries = store.pool_summaries()
    assert len(summaries) == 1
    s = summaries[0]
    assert s.pool_id == "pool1"
    assert s.blocks_minted == 2
    assert s.delegators == 1
    assert s.pledge == 1_000_000
    assert abs(s.margin - 0.03) < 1e-9

    detail = store.pool_detail("pool1")
    assert detail is not None
    assert detail.blocks_minted == 2
    assert store.pool_detail("unknown") is None
    assert store.recent_blocks_by_pool("pool1") == ["b2", "b1"]
    store.close()


def test_account_state_snapshot() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(1, 10, "b1", "genesis", txs=(Tx("tx1", certificates=(StakeRegistration("cred1"),)),))
    )
    assert store.registered_stake_credentials() == ["cred1"]

    store.record_account_states([AccountState("cred1", "poolX", 1_000_000)])
    state = store.account_state("cred1")
    assert state is not None
    assert state.delegated_pool == "poolX"
    assert state.reward == 1_000_000
    assert store.account_state("unknown") is None
    store.close()


def test_live_stake_and_saturation() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(
            1,
            10,
            "b1",
            "genesis",
            txs=(Tx("tx1", certificates=(PoolRegistration("pool1", 1000, 0.03, "r"),)),),
            issuer="pool1",
        )
    )
    # Record a live-stake snapshot: pool1 holds 0.2% of stake; n_opt = 500.
    store.record_stake_distribution({"pool1": 0.002}, n_opt=500)

    summary = store.pool_detail("pool1")
    assert summary is not None
    assert abs(summary.live_stake - 0.002) < 1e-9
    # saturation = live_stake * n_opt = 0.002 * 500 = 1.0 (fully saturated).
    assert abs(summary.saturation - 1.0) < 1e-9
    store.close()


def test_a_pool_registration_makes_the_pool_active() -> None:
    store = SqliteStore()
    reg = PoolRegistration(pool_id="pool1", pledge=1000, margin=0.03, reward_address="stake_x")
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", certificates=(reg,)),)))

    assert store.pools() == ("pool1",)
    store.close()


def test_a_retired_pool_drops_out_of_the_active_set() -> None:
    store = SqliteStore()
    reg = PoolRegistration(pool_id="pool1", pledge=1000, margin=0.03, reward_address="stake_x")
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", certificates=(reg,)),)))
    retire = PoolRetirement(pool_id="pool1", retiring_epoch=5)
    store.apply_block(blk(2, "b2", "b1", (Tx("tx2", certificates=(retire,)),)))

    assert store.pools() == ()
    store.close()


def test_delegation_tracks_the_latest_pool() -> None:
    store = SqliteStore()
    certs = (
        StakeRegistration(stake_address="stake_alice"),
        StakeDelegation(stake_address="stake_alice", pool_id="pool1"),
    )
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", certificates=certs),)))
    assert store.delegation_of("stake_alice") == "pool1"

    # Alice re-delegates to pool2.
    redelegate = StakeDelegation(stake_address="stake_alice", pool_id="pool2")
    store.apply_block(blk(2, "b2", "b1", (Tx("tx2", certificates=(redelegate,)),)))
    assert store.delegation_of("stake_alice") == "pool2"

    assert store.delegation_of("stake_nobody") is None
    store.close()


def test_registration_and_deregistration_track_the_latest_event() -> None:
    store = SqliteStore()
    store.apply_block(
        blk(1, "b1", "genesis", (Tx("tx1", certificates=(StakeRegistration("stake_alice"),)),))
    )
    assert store.is_stake_registered("stake_alice") is True
    assert store.is_stake_registered("stake_bob") is False

    store.apply_block(
        blk(2, "b2", "b1", (Tx("tx2", certificates=(StakeDeregistration("stake_alice"),)),))
    )
    assert store.is_stake_registered("stake_alice") is False

    # Re-registering flips it back on, and it must survive later blocks.
    store.apply_block(
        blk(3, "b3", "b2", (Tx("tx3", certificates=(StakeRegistration("stake_alice"),)),))
    )
    assert store.is_stake_registered("stake_alice") is True
    store.close()


def test_staking_certificates_roll_back_with_their_block() -> None:
    store = SqliteStore()
    store.apply_block(
        blk(
            1,
            "b1",
            "genesis",
            (
                Tx(
                    "tx1",
                    certificates=(
                        PoolRegistration("pool1", 1000, 0.03, "stake_x"),
                        StakeDelegation("stake_alice", "pool1"),
                    ),
                ),
            ),
        )
    )
    # A second block registers another pool and re-delegates.
    store.apply_block(
        blk(
            2,
            "b2",
            "b1",
            (Tx("tx2", certificates=(PoolRegistration("pool2", 2000, 0.01, "stake_y"),)),),
        )
    )
    assert set(store.pools()) == {"pool1", "pool2"}

    # Roll back block 2. pool2 and its rows must vanish; block 1's stay.
    store.rollback_to(blk(1, "b1", "genesis", ()).point)

    assert store.pools() == ("pool1",)
    assert store.delegation_of("stake_alice") == "pool1"
    store.close()
