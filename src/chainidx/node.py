"""A chain source that speaks to a cardano-node directly.

This is the from-scratch replacement for Ogmios. It opens the node's Unix socket,
runs the handshake (chapter 11), and then drives the chain-sync mini-protocol
(chapter 12) to follow the chain - producing exactly the same ``RollForward`` and
``RollBackward`` events as the Ogmios source. Because it satisfies the same
``ChainSource`` interface, the follower from chapter 09 drives it unchanged.

    README line earned here: "originally built on Ogmios, then rebuilt on my own
    from-scratch implementation of the Ouroboros chain-sync mini-protocol."

Like the Ogmios client, this file is the plumbing (sockets and the request/reply
loop) and is excluded from the unit-test coverage gate; all the message logic it
uses lives in the pure, fully-tested ``chainsync`` and ``cbor_blocks`` modules. It
is exercised by the integration test against a live cardonnay cluster.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from chainidx import chainsync
from chainidx.handshake import negotiate
from chainidx.model import Origin, Point
from chainidx.mux import PROTOCOL_CHAIN_SYNC, MuxConnection
from chainidx.source import ChainEvent

# cardonnay's local clusters use network magic 42.
_DEFAULT_MAGIC = 42


class NodeSource:
    """A ``ChainSource`` that talks to a cardano-node over its socket."""

    def __init__(self, socket_path: str, network_magic: int = _DEFAULT_MAGIC) -> None:
        self._socket_path = socket_path
        self._magic = network_magic
        self._mux: MuxConnection | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def _connect(self) -> MuxConnection:
        if self._mux is None:
            reader, writer = await asyncio.open_unix_connection(self._socket_path)
            self._writer = writer
            mux = MuxConnection(reader, writer)
            await negotiate(mux, self._magic)
            self._mux = mux
        return self._mux

    async def find_intersection(self, points: Sequence[Point | Origin]) -> Point | Origin | None:
        mux = await self._connect()
        message = chainsync.find_intersect_message(list(points))
        await mux.send(PROTOCOL_CHAIN_SYNC, chainsync.encode(message))
        return chainsync.parse_intersect_reply(await mux.receive(PROTOCOL_CHAIN_SYNC))

    async def next_event(self) -> ChainEvent:
        mux = await self._connect()
        await mux.send(PROTOCOL_CHAIN_SYNC, chainsync.encode(chainsync.request_next_message()))
        while True:
            event = chainsync.parse_next_reply(await mux.receive(PROTOCOL_CHAIN_SYNC))
            if event is not None:
                return event
            # MsgAwaitReply: the node has nothing new yet. It will send the block
            # when it has one, without us asking again.

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
            self._mux = None
