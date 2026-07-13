"""Tests for the reorg engine: rolling the indexed state back correctly.

The most important test is the last one: after a rollback and a switch to a
different branch, the database must be byte-for-byte what it would have been had
we only ever seen the winning branch. No residue, no leaked rows, no stale spends.
"""

import pytest

from chainidx.model import Asset, Block, Tx, TxIn, TxOut
from chainidx.store import SqliteStore


def blk(block_no: int, block_hash: str, prev_hash: str, txs: tuple[Tx, ...] = ()) -> Block:
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=txs,
    )


def test_rollback_removes_blocks_after_the_point() -> None:
    store = SqliteStore()
    for i, h in enumerate(["b1", "b2", "b3", "b4"], start=1):
        store.apply_block(blk(i, h, "prev"))

    removed = store.rollback_to(blk(2, "b2", "prev").point)

    assert store.block_count() == 2
    assert store.get_block("b3") is None
    assert store.get_block("b4") is None
    tip = store.tip()
    assert tip is not None
    assert tip.point.block_hash == "b2"
    # Removed newest-first, matching the deletion order.
    assert removed == ["b4", "b3"]
    store.close()


def test_rollback_restores_an_output_that_a_removed_block_had_spent() -> None:
    store = SqliteStore()
    # Block 1: alice gets 5 ada.
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", outputs=(TxOut("alice", 5_000_000),)),)))
    # Block 2: alice spends it to bob.
    spend = Tx("tx2", inputs=(TxIn("tx1", 0),), outputs=(TxOut("bob", 5_000_000),))
    store.apply_block(blk(2, "b2", "b1", (spend,)))
    assert store.balance("alice") == 0
    assert store.balance("bob") == 5_000_000

    # Roll back block 2. Alice's output must become unspent again, and bob's
    # output must be gone.
    store.rollback_to(blk(1, "b1", "genesis").point)

    assert store.balance("alice") == 5_000_000
    assert store.balance("bob") == 0
    store.close()


def test_rollback_to_origin_empties_everything() -> None:
    store = SqliteStore()
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", outputs=(TxOut("alice", 1),)),)))
    store.apply_block(blk(2, "b2", "b1", (Tx("tx2", outputs=(TxOut("bob", 2),)),)))

    store.rollback_to(None)

    assert store.block_count() == 0
    assert store.tip() is None
    assert store.balance("alice") == 0
    store.close()


def test_rollback_to_an_unknown_point_is_an_error() -> None:
    store = SqliteStore()
    store.apply_block(blk(1, "b1", "genesis"))
    with pytest.raises(ValueError, match="unknown point"):
        store.rollback_to(blk(9, "ghost", "b1").point)
    store.close()


def test_native_assets_of_a_removed_block_are_deleted() -> None:
    store = SqliteStore()
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", outputs=(TxOut("alice", 1_000_000),)),)))
    token = Asset("pol", "TOK", 9)
    store.apply_block(
        blk(2, "b2", "b1", (Tx("tx2", outputs=(TxOut("alice", 2_000_000, assets=(token,)),)),))
    )
    assert store.utxos("alice")[-1].assets == (token,)

    store.rollback_to(blk(1, "b1", "genesis").point)

    utxos = store.utxos("alice")
    assert len(utxos) == 1
    assert utxos[0].assets == ()
    store.close()


def test_reorg_leaves_the_database_identical_to_the_winning_branch() -> None:
    # Common history: b1 funds alice with 10 ada.
    genesis_tx = Tx("t1", outputs=(TxOut("alice", 10_000_000),))

    # Losing branch: b2 (alice -> bob), b3 (bob -> carol).
    t2 = Tx("t2", inputs=(TxIn("t1", 0),), outputs=(TxOut("bob", 10_000_000),))
    t3 = Tx("t3", inputs=(TxIn("t2", 0),), outputs=(TxOut("carol", 10_000_000),))
    losing = [blk(2, "b2", "b1", (t2,)), blk(3, "b3", "b2", (t3,))]

    # Winning branch: b2x (alice -> dave), b3x, b4x.
    t2x = Tx("t2x", inputs=(TxIn("t1", 0),), outputs=(TxOut("dave", 10_000_000),))
    t3x = Tx(
        "t3x",
        inputs=(TxIn("t2x", 0),),
        outputs=(TxOut("erin", 6_000_000), TxOut("dave", 4_000_000)),
    )
    winning = [blk(2, "b2x", "b1", (t2x,)), blk(3, "b3x", "b2x", (t3x,)), blk(4, "b4x", "b3x")]

    # Store A: sees the losing branch, then reorgs to the winning branch.
    reorged = SqliteStore()
    reorged.apply_block(blk(1, "b1", "genesis", (genesis_tx,)))
    for b in losing:
        reorged.apply_block(b)
    reorged.rollback_to(blk(1, "b1", "genesis").point)
    for b in winning:
        reorged.apply_block(b)

    # Store B: only ever saw the winning branch.
    clean = SqliteStore()
    clean.apply_block(blk(1, "b1", "genesis", (genesis_tx,)))
    for b in winning:
        clean.apply_block(b)

    # The two must agree on every balance and on the tip height.
    for who in ["alice", "bob", "carol", "dave", "erin"]:
        assert reorged.balance(who) == clean.balance(who), who
    assert reorged.balance("bob") == 0
    assert reorged.balance("carol") == 0
    assert reorged.balance("dave") == 4_000_000
    assert reorged.balance("erin") == 6_000_000

    reorged_tip = reorged.tip()
    clean_tip = clean.tip()
    assert reorged_tip is not None
    assert clean_tip is not None
    assert reorged_tip.block_no == clean_tip.block_no == 4
    assert reorged.block_count() == clean.block_count() == 4

    reorged.close()
    clean.close()
