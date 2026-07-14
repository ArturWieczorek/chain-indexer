"""A local-state-query client: read ledger state from a live node.

This drives the LSQ mini-protocol over the node socket: handshake, acquire the
volatile tip, run a batch of queries, release, and return a `LedgerSnapshot`. It
reuses the mux (`MuxConnection`) and the handshake from chapters 11 and 12, adding
mini-protocol id 7.

Like the other socket-bound clients (`ogmios.py`, `node.py`), this is excluded
from the unit-test coverage gate; the pure message and result logic it uses lives
in the fully-tested `statequery` module. A local cluster produces blocks very
fast, so the acquired tip can be superseded mid-query and the node drops the
connection; `snapshot` therefore retries a few times, which is normal for LSQ
against a busy node.
"""

from __future__ import annotations

import asyncio
from typing import Any

import cbor2

from chainidx import statequery
from chainidx.handshake import negotiate
from chainidx.model import LedgerSnapshot
from chainidx.mux import PROTOCOL_LOCAL_STATE_QUERY as LSQ
from chainidx.mux import MuxConnection

_DEFAULT_MAGIC = 42


class LocalStateClient:
    """Reads a `LedgerSnapshot` from a node over local-state-query."""

    def __init__(self, socket_path: str, network_magic: int = _DEFAULT_MAGIC) -> None:
        self._socket_path = socket_path
        self._magic = network_magic

    async def snapshot(self, retries: int = 8) -> LedgerSnapshot:
        last: Exception | None = None
        for _ in range(retries):
            try:
                return await asyncio.wait_for(self._snapshot_once(), 12)
            except (EOFError, OSError, RuntimeError, TimeoutError) as exc:
                last = exc
                await asyncio.sleep(0.5)
        raise RuntimeError(f"local-state-query failed after {retries} tries: {last}")

    async def _snapshot_once(self) -> LedgerSnapshot:
        reader, writer = await asyncio.open_unix_connection(self._socket_path)
        try:
            mux = MuxConnection(reader, writer)
            await negotiate(mux, self._magic)

            await mux.send(LSQ, cbor2.dumps(statequery.acquire_message()))
            acquired = await mux.receive(LSQ)
            if acquired[0] != 1:
                raise RuntimeError(f"could not acquire ledger state: {acquired!r}")

            epoch = statequery.parse_epoch(await self._query(mux, statequery.epoch_query()))
            system_start = statequery.parse_system_start(
                await self._query(mux, statequery.system_start_message())
            )
            params = statequery.parse_protocol_params(
                await self._query(mux, statequery.protocol_params_query())
            )
            pools = statequery.parse_stake_pools(
                await self._query(mux, statequery.stake_pools_query())
            )
            distribution = statequery.parse_stake_distribution(
                await self._query(mux, statequery.stake_distribution_query())
            )

            await mux.send(LSQ, cbor2.dumps(statequery.release_message()))
            return LedgerSnapshot(
                epoch=epoch,
                system_start=system_start,
                protocol_params=params,
                stake_pools=pools,
                stake_distribution=distribution,
            )
        finally:
            writer.close()

    async def _query(self, mux: MuxConnection, message: list[Any]) -> list[Any]:
        await mux.send(LSQ, cbor2.dumps(message))
        reply = await mux.receive(LSQ)
        if reply[0] != 4:
            raise RuntimeError(f"query failed: {reply!r}")
        result: list[Any] = reply[1]
        return result
