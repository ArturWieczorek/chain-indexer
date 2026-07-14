"""The local-tx-monitor mini-protocol codec (mempool inspection).

This is the fifth and last node-to-client mini-protocol (id 9). It lets a client
**acquire** a snapshot of the node's mempool, then ask about it: its size, and the
pending transactions one at a time. Like chain-sync and local-state-query, the
messages are small CBOR arrays tagged by an integer, confirmed against a live node
before this code was written:

- ``MsgAcquire   = [1]``            -> ``MsgAcquired = [2, slot]``
- ``MsgRelease   = [3]``
- ``MsgNextTx    = [5]``            -> ``[6]`` (no more) or ``[6, [era, tx]]``
- ``MsgGetSizes  = [9]``            -> ``[10, [capacity, size, numberOfTxs]]``
- ``MsgDone      = [0]``

A mempool transaction arrives as ``[eraId, CBORTag(24, <tx bytes>)]``; its id is
the blake2b-256 of the transaction body's bytes, computed with
``cbor_blocks.tx_id_of_bytes``.

This module is pure (no socket) and fully unit-tested; the socket-bound client that
uses it, ``MempoolClient``, lives below and is excluded from the coverage gate like
the other integration clients.
"""

from __future__ import annotations

from typing import Any

from chainidx.cbor_blocks import tx_id_of_bytes


def acquire_message() -> list[Any]:
    """MsgAcquire: take a consistent snapshot of the current mempool."""
    return [1]


def release_message() -> list[Any]:
    """MsgRelease: drop the snapshot."""
    return [3]


def done_message() -> list[Any]:
    """MsgDone: end the mini-protocol."""
    return [0]


def next_tx_message() -> list[Any]:
    """MsgNextTx: ask for the next pending transaction in the snapshot."""
    return [5]


def get_sizes_message() -> list[Any]:
    """MsgGetSizes: ask for the mempool's capacity, fill, and transaction count."""
    return [9]


def parse_acquired(reply: list[Any]) -> int:
    """Return the slot the mempool snapshot was acquired at (``[2, slot]``)."""
    if reply[0] != 2:
        raise RuntimeError(f"could not acquire mempool: {reply!r}")
    return int(reply[1])


def parse_sizes(reply: list[Any]) -> tuple[int, int, int]:
    """Return ``(capacity, size, tx_count)`` from ``[10, [capacity, size, n]]``."""
    if reply[0] != 10:
        raise RuntimeError(f"unexpected get-sizes reply: {reply!r}")
    capacity, size, count = reply[1]
    return int(capacity), int(size), int(count)


def parse_next_tx(reply: list[Any]) -> str | None:
    """Return the next pending transaction's id, or ``None`` at the end.

    ``[6]`` means no more transactions; ``[6, [era, CBORTag(24, bytes)]]`` carries
    one, whose id we compute from the wrapped transaction bytes.
    """
    if reply[0] != 6:
        raise RuntimeError(f"unexpected next-tx reply: {reply!r}")
    if len(reply) == 1:
        return None
    wrapped = reply[1][1]  # [era, CBORTag(24, tx bytes)]
    return tx_id_of_bytes(wrapped.value)
