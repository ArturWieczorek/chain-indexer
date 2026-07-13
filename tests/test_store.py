"""Tests for the SQLite store: schema, migrations, and block persistence."""

from pathlib import Path

from chainidx.model import Block, Tx
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
