"""A local-tx-submission client: hand a signed transaction to the node.

This drives the local-tx-submission mini-protocol (chapter 45): handshake, send the
transaction, read the node's accept or reject, done. It reuses the mux and
handshake and the pure codec in ``txsubmit``, adding mini-protocol id 6.

Like the other socket-bound clients, it is excluded from the unit-test coverage
gate; its message logic lives in the fully tested ``txsubmit`` module.
"""

from __future__ import annotations

import asyncio

import cbor2

from chainidx import txsubmit
from chainidx.handshake import negotiate
from chainidx.model import SubmitResult
from chainidx.mux import PROTOCOL_LOCAL_TX_SUBMISSION as TXSUBMIT
from chainidx.mux import MuxConnection

_DEFAULT_MAGIC = 42


class TxSubmitClient:
    """Submits a signed transaction to a node over local-tx-submission."""

    def __init__(self, socket_path: str, network_magic: int = _DEFAULT_MAGIC) -> None:
        self._socket_path = socket_path
        self._magic = network_magic

    async def submit(self, tx_bytes: bytes) -> SubmitResult:
        return await asyncio.wait_for(self._submit_once(tx_bytes), 12)

    async def _submit_once(self, tx_bytes: bytes) -> SubmitResult:
        reader, writer = await asyncio.open_unix_connection(self._socket_path)
        try:
            mux = MuxConnection(reader, writer)
            await negotiate(mux, self._magic)
            await mux.send(TXSUBMIT, cbor2.dumps(txsubmit.submit_message(tx_bytes)))
            result = txsubmit.parse_reply(await mux.receive(TXSUBMIT))
            await mux.send(TXSUBMIT, cbor2.dumps(txsubmit.done_message()))
            return result
        finally:
            writer.close()

    def submit_sync(self, tx_bytes: bytes) -> SubmitResult:
        """A blocking wrapper, for the command-line interface."""
        return asyncio.run(self.submit(tx_bytes))
