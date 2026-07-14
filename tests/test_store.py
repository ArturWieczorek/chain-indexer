"""Tests for the SQLite store: schema, migrations, and block persistence."""

from pathlib import Path

from chainidx.model import Asset, Block, GovActionProposal, GovVote, Tx, TxIn, TxOut
from chainidx.patterns import Pattern
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


def test_epoch_stats_totals_blocks_txs_and_fees() -> None:
    store = SqliteStore()
    # Epoch 0 (slot 10): one block, two txs paying 100 + 50 in fees.
    store.apply_block(block(1, "b1", "genesis", txs=(Tx("t1", fee=100), Tx("t2", fee=50))))
    # Epoch 1 (slot 110): one block, one tx paying 200.
    store.apply_block(Block(11, 110, "b11", "b1", txs=(Tx("t3", fee=200),)))
    stats = store.epoch_stats(100)
    assert stats[0].epoch_no == 1  # newest epoch first
    by_epoch = {s.epoch_no: s for s in stats}
    assert by_epoch[0].block_count == 1
    assert by_epoch[0].tx_count == 2
    assert by_epoch[0].fee_total == 150
    assert by_epoch[1].fee_total == 200
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


# A 57-byte base address (header + 28-byte payment cred + 28-byte stake cred),
# so the store derives its stake credential the way a real address would.
_BASE_ADDR = "00" + "11" * 28 + "22" * 28
_STAKE_CRED = "22" * 28


def _matches_store() -> SqliteStore:
    """A store with one spent output and two unspent ones, for match queries."""
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
                        TxOut(_BASE_ADDR, 5_000_000, assets=(Asset("polX", "4869", 1),)),
                        TxOut("addrPlain", 2_000_000),
                    ),
                ),
                # tx2 spends tx1's first output, so it becomes spent.
                Tx("tx2", inputs=(TxIn("tx1", 0),), outputs=(TxOut("addrOther", 1_000_000),)),
            ),
        )
    )
    return store


def test_matches_by_address_respects_spent_status() -> None:
    store = _matches_store()
    pattern = Pattern("address", _BASE_ADDR)
    assert store.matches(pattern, "unspent") == ()  # the output was spent by tx2
    spent = store.matches(pattern, "spent")
    assert len(spent) == 1
    assert spent[0].tx_hash == "tx1"
    assert spent[0].output_index == 0
    assert spent[0].lovelace == 5_000_000
    assert spent[0].spent is True
    assert spent[0].assets == (Asset("polX", "4869", 1),)
    assert store.matches(pattern, "all") == spent
    store.close()


def test_matches_by_stake_policy_and_asset() -> None:
    store = _matches_store()
    assert len(store.matches(Pattern("stake", _STAKE_CRED), "all")) == 1
    assert len(store.matches(Pattern("policy", "polX"), "all")) == 1
    assert len(store.matches(Pattern("asset", "polX", "4869"), "all")) == 1
    assert store.matches(Pattern("asset", "polX", "beef"), "all") == ()
    store.close()


def test_matches_all_and_unknown_kind() -> None:
    store = _matches_store()
    unspent = store.matches(Pattern("all"), "unspent")
    assert {m.address for m in unspent} == {"addrPlain", "addrOther"}
    assert len(store.matches(Pattern("all"), "all")) == 3
    assert len(store.matches(Pattern("all"), "spent")) == 1
    assert store.matches(Pattern("nonsense"), "all") == ()  # unrecognised kind
    store.close()


def test_get_datum_and_datum_hash_on_matches() -> None:
    store = SqliteStore()
    store.apply_block(
        block(
            1,
            "b1",
            "genesis",
            txs=(
                Tx("tx1", outputs=(TxOut("addrD", 2_000_000, datum="d87980", datum_hash="ab12"),)),
            ),
        )
    )
    # The datum is looked up by its hash, and returned None for an unknown one.
    assert store.get_datum("ab12") == "d87980"
    assert store.get_datum("nope") is None
    # The hash rides along on a match, too.
    hit = store.matches(Pattern("address", "addrD"), "all")
    assert hit[0].datum == "d87980"
    assert hit[0].datum_hash == "ab12"
    store.close()


def test_get_script_by_hash() -> None:
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
                            "addrS",
                            2_000_000,
                            reference_script_hash="bb7d",
                            reference_script_type="plutusV3",
                            reference_script="8203aa",
                        ),
                    ),
                ),
            ),
        )
    )
    assert store.get_script("bb7d") == ("plutusV3", "8203aa")
    assert store.get_script("nope") is None
    store.close()
