"""Tests for the SQLite store: schema, migrations, and block persistence."""

from pathlib import Path

from chainidx.model import Asset, Block, GovActionProposal, GovVote, Tx, TxOut
from chainidx.store import SqliteStore


def block(block_no: int, block_hash: str, prev_hash: str, txs: tuple[Tx, ...] = ()) -> Block:
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=txs,
    )


def test_a_fresh_store_is_empty() -> None:
    store = SqliteStore()
    assert store.block_count() == 0
    assert store.tip() is None
    store.close()


def test_apply_block_persists_a_block() -> None:
    store = SqliteStore()
    store.apply_block(block(1, "b1", "genesis"))

    assert store.block_count() == 1
    tip = store.tip()
    assert tip is not None
    assert tip.block_no == 1
    assert tip.point.block_hash == "b1"
    assert tip.point.slot_no == 10
    store.close()


def test_get_block_preserves_the_issuer() -> None:
    store = SqliteStore()
    store.apply_block(
        Block(block_no=1, slot_no=10, block_hash="b1", prev_hash="genesis", txs=(), issuer="poolX")
    )
    fetched = store.get_block("b1")
    assert fetched is not None
    assert fetched.issuer == "poolX"
    store.close()


def test_get_block_round_trips_with_its_transactions() -> None:
    store = SqliteStore()
    txs = (Tx(tx_id="tx_a"), Tx(tx_id="tx_b"))
    store.apply_block(block(1, "b1", "genesis", txs=txs))

    fetched = store.get_block("b1")
    assert fetched is not None
    assert fetched.block_no == 1
    assert fetched.prev_hash == "genesis"
    # Transactions come back in block order.
    assert [t.tx_id for t in fetched.txs] == ["tx_a", "tx_b"]
    store.close()


def test_get_block_returns_none_for_an_unknown_hash() -> None:
    store = SqliteStore()
    assert store.get_block("nope") is None
    store.close()


def test_epoch_summaries_group_blocks_by_slot() -> None:
    store = SqliteStore()
    # block i is at slot i*10; with epoch_length 100, epoch = slot // 100.
    for i in range(1, 13):
        store.apply_block(block(i, f"b{i}", "p"))

    summaries = store.epoch_summaries(100)
    assert summaries[0].epoch_no == 1  # newest epoch first
    by_epoch = {s.epoch_no: s for s in summaries}
    assert by_epoch[0].block_count == 9  # slots 10..90
    assert by_epoch[1].block_count == 3  # slots 100..120

    one = store.epoch_summary(0, 100)
    assert one is not None
    assert one.block_count == 9
    assert one.start_slot == 10
    assert store.epoch_summary(999, 100) is None
    store.close()


def test_get_block_by_number_and_slot() -> None:
    store = SqliteStore()
    store.apply_block(block(7, "b7", "b6"))  # slot 70 (block_no * 10)

    by_number = store.get_block_by_number(7)
    assert by_number is not None
    assert by_number.block_hash == "b7"

    by_slot = store.get_block_by_slot(70)
    assert by_slot is not None
    assert by_slot.block_hash == "b7"

    assert store.get_block_by_number(999) is None
    assert store.get_block_by_slot(999) is None
    store.close()


def test_total_transactions_counts_across_blocks() -> None:
    store = SqliteStore()
    store.apply_block(block(1, "b1", "genesis", txs=(Tx("t1"), Tx("t2"))))
    store.apply_block(block(2, "b2", "b1", txs=(Tx("t3"),)))
    assert store.total_transactions() == 3
    store.close()


def test_the_tip_is_the_most_recently_applied_block() -> None:
    store = SqliteStore()
    for i, h in enumerate(["b1", "b2", "b3"], start=1):
        store.apply_block(block(i, h, "prev"))
    tip = store.tip()
    assert tip is not None
    assert tip.point.block_hash == "b3"
    assert tip.block_no == 3
    store.close()


def test_data_survives_reopening_the_database(tmp_path: Path) -> None:
    db = str(tmp_path / "chain.db")

    first = SqliteStore(db)
    first.apply_block(block(1, "b1", "genesis"))
    first.close()

    # Reopening runs migrations again, but they are versioned, so the schema is
    # left alone and the data is still there.
    second = SqliteStore(db)
    assert second.block_count() == 1
    assert second.get_block("b1") is not None
    second.close()


def test_store_works_as_a_context_manager() -> None:
    with SqliteStore() as store:
        store.apply_block(block(1, "b1", "genesis"))
        assert store.block_count() == 1


def test_drep_votes_resolves_action_type_and_marks_unknown() -> None:
    store = SqliteStore()
    store.apply_block(
        block(
            1,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    proposals=(GovActionProposal("g1", "InfoAction", 0, "r"),),
                    votes=(
                        GovVote("g1", "DRep", "drep1", "Yes"),
                        # A vote on an action we have not indexed -> type Unknown.
                        GovVote("g_elsewhere", "DRep", "drep1", "No"),
                    ),
                ),
            ),
        )
    )
    votes = store.drep_votes("drep1")
    by_action = {v.gov_action_id: v for v in votes}
    assert by_action["g1"].action_type == "InfoAction"
    assert by_action["g1"].vote == "Yes"
    assert by_action["g_elsewhere"].action_type == "Unknown"
    store.close()


def test_policy_detail_groups_assets_under_a_policy() -> None:
    store = SqliteStore()
    store.apply_block(
        block(
            1,
            "b1",
            "genesis",
            txs=(
                Tx(
                    "tx1",
                    outputs=(
                        TxOut(
                            "addrA",
                            2_000_000,
                            assets=(Asset("polX", "436861696e", 1), Asset("polX", "0a", 5)),
                        ),
                    ),
                ),
            ),
        )
    )
    detail = store.policy_detail("polX")
    assert detail is not None
    assert detail.asset_count == 2
    assert {a.asset_name for a in detail.assets} == {"436861696e", "0a"}
    assert store.policy_detail("nope") is None
    store.close()


def test_blocks_in_epoch_lists_blocks_newest_first() -> None:
    store = SqliteStore()
    for i in range(1, 13):  # block i at slot i*10; epoch_length 100
        store.apply_block(block(i, f"b{i}", "p" if i == 1 else f"b{i - 1}"))
    epoch0 = store.blocks_in_epoch(0, 100)
    assert [b.block_no for b in epoch0] == [9, 8, 7, 6, 5, 4, 3, 2, 1]
    assert [b.block_no for b in store.blocks_in_epoch(1, 100)] == [12, 11, 10]
    assert store.blocks_in_epoch(99, 100) == []
    store.close()
