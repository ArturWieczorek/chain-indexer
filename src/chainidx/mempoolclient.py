"""A local-tx-monitor client: read the node's mempool over its socket.

This drives the local-tx-monitor mini-protocol (chapter 43): handshake, acquire a
mempool snapshot, read its sizes and the pending transaction ids, release. It
reuses the mux and handshake from chapters 11-12 and the pure codec in
``txmonitor``, adding mini-protocol id 9.

Like the other socket-bound clients (``localstate.py``, ``node.py``), it is
excluded from the unit-test coverage gate; its message and id logic lives in the
fully tested ``txmonitor`` module.
"""

from __future__ import annotations

import asyncio

import cbor2

from chainidx import txmonitor
from chainidx.handshake import negotiate
from chainidx.model import MempoolStatus
from chainidx.mux import PROTOCOL_LOCAL_TX_MONITOR as MEMPOOL
from chainidx.mux import MuxConnection

_DEFAULT_MAGIC = 42


class MempoolClient:
    """Reads a `MempoolStatus` snapshot from a node's mempool."""

    def __init__(self, socket_path: str, network_magic: int = _DEFAULT_MAGIC) -> None:
        self._socket_path = socket_path
        self._magic = network_magic

    async def status(self, max_txs: int = 100) -> MempoolStatus:
        return await asyncio.wait_for(self._status_once(max_txs), 12)

    async def _status_once(self, max_txs: int) -> MempoolStatus:
        reader, writer = await asyncio.open_unix_connection(self._socket_path)
        try:
            mux = MuxConnection(reader, writer)
            await negotiate(mux, self._magic)

            await mux.send(MEMPOOL, cbor2.dumps(txmonitor.acquire_message()))
            slot = txmonitor.parse_acquired(await mux.receive(MEMPOOL))

            await mux.send(MEMPOOL, cbor2.dumps(txmonitor.get_sizes_message()))
            capacity, size, count = txmonitor.parse_sizes(await mux.receive(MEMPOOL))

            tx_ids: list[str] = []
            for _ in range(max_txs):
                await mux.send(MEMPOOL, cbor2.dumps(txmonitor.next_tx_message()))
                tx_id = txmonitor.parse_next_tx(await mux.receive(MEMPOOL))
                if tx_id is None:
                    break
                tx_ids.append(tx_id)

            await mux.send(MEMPOOL, cbor2.dumps(txmonitor.release_message()))
            await mux.send(MEMPOOL, cbor2.dumps(txmonitor.done_message()))
            return MempoolStatus(
                slot=slot,
                capacity=capacity,
                size_bytes=size,
                tx_count=count,
                tx_ids=tuple(tx_ids),
            )
        finally:
            writer.close()

    def status_sync(self, max_txs: int = 100) -> MempoolStatus:
        """A blocking wrapper, for the synchronous API request handler."""
        return asyncio.run(self.status(max_txs))
