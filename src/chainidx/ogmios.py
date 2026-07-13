"""An Ogmios-backed chain source.

Ogmios is a small bridge that connects to a cardano-node, speaks the node's
mini-protocols, and exposes them as a JSON-RPC WebSocket API. Pointing our
indexer at Ogmios is the fastest way to get real chain data flowing: we send
``findIntersection`` and ``nextBlock`` requests and receive JSON we already know
how to parse (``ogmios_parse``).

This module is the *plumbing* - opening the WebSocket and shuttling JSON. All the
interesting translation lives in the pure ``ogmios_parse`` functions, which are
unit-tested against saved responses. Because this file needs a live Ogmios
server to do anything, it is excluded from the unit-test coverage gate and
exercised only by the integration test (``tests/test_ogmios_integration.py``),
which runs against a cardonnay cluster.

Run one locally with:

    ogmios --node-socket <cluster>/bft1.socket --node-config <cluster>/config-bft1.json

In chapter 12 we replace this with our own implementation of the wire protocol,
and the sync loop does not change, because both satisfy the same ``ChainSource``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import websockets

from chainidx.model import Origin, Point
from chainidx.ogmios_parse import parse_next_block, parse_point, to_ogmios_point
from chainidx.source import ChainEvent

_DEFAULT_URL = "ws://127.0.0.1:1337"


class OgmiosSource:
    """A ``ChainSource`` that reads from an Ogmios WebSocket."""

    def __init__(self, url: str = _DEFAULT_URL) -> None:
        self._url = url
        self._ws: Any = None

    async def _connect(self) -> Any:
        if self._ws is None:
            self._ws = await websockets.connect(self._url, max_size=None)
        return self._ws

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        ws = await self._connect()
        await ws.send(json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}))
        reply: dict[str, Any] = json.loads(await ws.recv())
        return reply

    async def find_intersection(self, points: Sequence[Point | Origin]) -> Point | Origin | None:
        reply = await self._rpc(
            "findIntersection", {"points": [to_ogmios_point(p) for p in points]}
        )
        result = reply.get("result", {})
        intersection = result.get("intersection")
        return None if intersection is None else parse_point(intersection)

    async def next_event(self) -> ChainEvent:
        reply = await self._rpc("nextBlock")
        return parse_next_block(reply["result"])

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
