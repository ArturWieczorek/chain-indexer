"""Tests for the CBOR block decoder, run against real captured node blocks.

The fixtures under tests/fixtures/node_block_*.cbor were captured from a live
cardano-node over its socket. The expected hashes below are the real on-chain
hashes, so these tests prove we decode identity correctly, not just plausibly.
"""

import io
from pathlib import Path
from typing import cast

import cbor2

from chainidx.cbor_blocks import _read_array_header, decode_block, decode_value
from chainidx.model import (
    DRepRegistration,
    PoolRegistration,
    StakeDelegation,
    StakeRegistration,
)
from chainidx.store import SqliteStore

FIXTURES = Path(__file__).parent / "fixtures"

# Real values for the captured block at height 33.
BLOCK_HASH = "7058a7c4d6faf83b7f563ade99f38a30c021c8701aad16f6f51d6bb5865d8608"
TX0_ID = "d97b618ecd7c2c9f804015547805bae59b6367566d81baf9a439f5f5fc744269"


def load_tag(name: str) -> cbor2.CBORTag:
    return cast(cbor2.CBORTag, cbor2.loads((FIXTURES / name).read_bytes()))


def test_decode_a_real_block_reproduces_the_on_chain_hashes() -> None:
    block = decode_block(load_tag("node_block_txs.cbor"))
    assert block.block_hash == BLOCK_HASH
    assert block.block_no == 33
    assert block.slot_no == 349
    assert block.prev_hash.startswith("7a41eb8cf2d6c991")
    assert len(block.txs) >= 1
    assert block.txs[0].tx_id == TX0_ID


def test_decoded_transaction_has_inputs_outputs_and_certificates() -> None:
    tx = decode_block(load_tag("node_block_txs.cbor")).txs[0]
    assert len(tx.inputs) >= 1
    assert len(tx.outputs) >= 1
    assert tx.outputs[0].lovelace > 0
    # An address is 57 raw bytes -> 114 hex characters.
    assert len(tx.outputs[0].address) == 114

    kinds = {type(c) for c in tx.certificates}
    assert PoolRegistration in kinds
    assert StakeRegistration in kinds
    assert StakeDelegation in kinds
    assert DRepRegistration in kinds
    pool = next(c for c in tx.certificates if isinstance(c, PoolRegistration))
    assert 0.0 <= pool.margin <= 1.0
    assert pool.pledge > 0


def test_decode_an_empty_block() -> None:
    block = decode_block(load_tag("node_block_empty.cbor"))
    assert len(block.block_hash) == 64
    assert block.txs == ()
    # The very first block builds on nothing, so prev_hash is empty.
    assert block.prev_hash == ""


def test_decoded_block_flows_into_the_store() -> None:
    block = decode_block(load_tag("node_block_txs.cbor"))
    store = SqliteStore()
    store.apply_block(block)
    assert store.block_count() == 1
    # The pools registered in this genesis-setup block show up.
    assert len(store.pools()) >= 1
    store.close()


def test_decode_value_handles_ada_and_multi_asset() -> None:
    lovelace, assets = decode_value(1_500_000)
    assert lovelace == 1_500_000
    assert assets == ()

    coin, assets = decode_value([2_000_000, {b"\xaa\xbb": {b"TOK": 5, b"OTH": 9}}])
    assert coin == 2_000_000
    quantities = {(a.policy_id, a.asset_name, a.quantity) for a in assets}
    assert quantities == {("aabb", "544f4b", 5), ("aabb", "4f5448", 9)}


def test_read_array_header_reads_short_and_long_forms() -> None:
    # 0x83 -> an array of 3 (length in the head byte).
    assert _read_array_header(io.BytesIO(bytes([0x83]))) == 3
    # 0x98 0x1e -> an array of 30 (one following length byte).
    assert _read_array_header(io.BytesIO(bytes([0x98, 30]))) == 30
