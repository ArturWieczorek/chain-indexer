"""Tests for transaction indexing: outputs, inputs, assets, and balances."""

from chainidx.model import Asset, Block, Tx, TxIn, TxOut
from chainidx.store import SqliteStore


def blk(block_no: int, block_hash: str, prev_hash: str, txs: tuple[Tx, ...]) -> Block:
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=txs,
    )


def test_outputs_credit_their_address() -> None:
    store = SqliteStore()
    tx = Tx(tx_id="tx1", outputs=(TxOut("alice", 1_000_000), TxOut("bob", 2_000_000)))
    store.apply_block(blk(1, "b1", "genesis", (tx,)))

    assert store.balance("alice") == 1_000_000
    assert store.balance("bob") == 2_000_000
    assert store.balance("nobody") == 0
    store.close()


def test_spending_an_output_removes_it_from_the_balance() -> None:
    store = SqliteStore()
    # Block 1: alice receives 5 ada in tx1, output index 0.
    fund = Tx(tx_id="tx1", outputs=(TxOut("alice", 5_000_000),))
    store.apply_block(blk(1, "b1", "genesis", (fund,)))
    assert store.balance("alice") == 5_000_000

    # Block 2: alice spends that output, sending 3 ada to bob (and 2 back).
    spend = Tx(
        tx_id="tx2",
        inputs=(TxIn(tx_id="tx1", index=0),),
        outputs=(TxOut("bob", 3_000_000), TxOut("alice", 2_000_000)),
    )
    store.apply_block(blk(2, "b2", "b1", (spend,)))

    assert store.balance("alice") == 2_000_000
    assert store.balance("bob") == 3_000_000
    store.close()


def test_native_assets_are_indexed_on_the_output() -> None:
    store = SqliteStore()
    token = Asset(policy_id="pol1", asset_name="GOLD", quantity=7)
    tx = Tx(tx_id="tx1", outputs=(TxOut("alice", 1_000_000, assets=(token,)),))
    store.apply_block(blk(1, "b1", "genesis", (tx,)))

    utxos = store.utxos("alice")
    assert len(utxos) == 1
    assert utxos[0].lovelace == 1_000_000
    assert utxos[0].assets == (token,)
    store.close()


def test_a_later_tx_can_spend_an_earlier_tx_in_the_same_block() -> None:
    store = SqliteStore()
    tx_a = Tx(tx_id="txA", outputs=(TxOut("alice", 4_000_000),))
    tx_b = Tx(
        tx_id="txB",
        inputs=(TxIn(tx_id="txA", index=0),),
        outputs=(TxOut("carol", 4_000_000),),
    )
    # Both in one block, in order. txB spends txA's output.
    store.apply_block(blk(1, "b1", "genesis", (tx_a, tx_b)))

    assert store.balance("alice") == 0
    assert store.balance("carol") == 4_000_000
    store.close()


def test_spending_an_output_we_never_indexed_is_harmless() -> None:
    store = SqliteStore()
    # This input references a tx we never saw (e.g. a genesis output when we
    # started syncing mid-chain). It should not crash and should change nothing.
    spend = Tx(
        tx_id="tx1",
        inputs=(TxIn(tx_id="unknown_tx", index=3),),
        outputs=(TxOut("alice", 1_000_000),),
    )
    store.apply_block(blk(1, "b1", "genesis", (spend,)))
    assert store.balance("alice") == 1_000_000
    store.close()


def test_utxos_lists_only_unspent_outputs() -> None:
    store = SqliteStore()
    fund = Tx(tx_id="tx1", outputs=(TxOut("alice", 1_000_000), TxOut("alice", 2_000_000)))
    store.apply_block(blk(1, "b1", "genesis", (fund,)))
    # Spend only the first output.
    spend = Tx(tx_id="tx2", inputs=(TxIn(tx_id="tx1", index=0),), outputs=(TxOut("bob", 1_000_000),))
    store.apply_block(blk(2, "b2", "b1", (spend,)))

    alice_utxos = store.utxos("alice")
    assert len(alice_utxos) == 1
    assert alice_utxos[0].lovelace == 2_000_000
    store.close()
