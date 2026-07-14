"""Tests for the local-tx-monitor codec, using a real captured mempool tx.

tests/fixtures/mempool_tx.cbor is the raw CBOR of a transaction we submitted to a
live cluster and read back out of the mempool; its real id is asserted below, so
these tests prove we compute the id the node does, not just plausibly.
"""

from pathlib import Path

import cbor2
import pytest

from chainidx import txmonitor
from chainidx.cbor_blocks import tx_id_of_bytes

FIXTURES = Path(__file__).parent / "fixtures"
TX_BYTES = (FIXTURES / "mempool_tx.cbor").read_bytes()
TX_ID = "9c494236319fcb70b90097c05a0da35e5d670fedef80d1618a587c951f1c4792"


def test_tx_id_of_bytes_reproduces_the_real_id() -> None:
    assert tx_id_of_bytes(TX_BYTES) == TX_ID


def test_message_builders() -> None:
    assert txmonitor.acquire_message() == [1]
    assert txmonitor.release_message() == [3]
    assert txmonitor.done_message() == [0]
    assert txmonitor.next_tx_message() == [5]
    assert txmonitor.get_sizes_message() == [9]


def test_parse_acquired_and_sizes() -> None:
    assert txmonitor.parse_acquired([2, 236491]) == 236491
    assert txmonitor.parse_sizes([10, [178176, 232, 1]]) == (178176, 232, 1)
    with pytest.raises(RuntimeError):
        txmonitor.parse_acquired([99])
    with pytest.raises(RuntimeError):
        txmonitor.parse_sizes([99])


def test_parse_next_tx_empty_and_with_transaction() -> None:
    # [6] means no more transactions.
    assert txmonitor.parse_next_tx([6]) is None
    # [6, [era, CBORTag(24, tx bytes)]] carries one; its id comes from the bytes.
    reply = [6, [6, cbor2.CBORTag(24, TX_BYTES)]]
    assert txmonitor.parse_next_tx(reply) == TX_ID
    with pytest.raises(RuntimeError):
        txmonitor.parse_next_tx([99])
