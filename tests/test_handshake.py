"""Tests for the handshake mini-protocol, using in-memory streams."""

import asyncio

import cbor2
import pytest

from chainidx.handshake import HandshakeError, negotiate, parse_reply, propose_message
from chainidx.mux import MuxConnection, pack_header


class FakeWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None


def test_propose_message_flags_each_version() -> None:
    message = propose_message(network_magic=42, versions=[9, 10])
    assert message[0] == 0
    table = message[1]
    # Each proposed version has the 0x8000 flag and carries [magic, query=False].
    assert set(table.keys()) == {0x8000 | 9, 0x8000 | 10}
    assert table[0x8000 | 9] == [42, False]


def test_parse_reply_accepts_and_strips_the_flag() -> None:
    # The node accepts node-to-client version 20 (0x8000 | 20 == 32788).
    assert parse_reply([1, 32788, [42, False]]) == 20


def test_parse_reply_raises_on_refusal() -> None:
    with pytest.raises(HandshakeError):
        parse_reply([2, ["versionMismatch", [9, 10]]])


async def test_negotiate_over_a_stream() -> None:
    reader = asyncio.StreamReader()
    accept = cbor2.dumps([1, 32788, [42, False]])
    reader.feed_data(pack_header(0, len(accept)) + accept)
    reader.feed_eof()
    writer = FakeWriter()
    mux = MuxConnection(reader, writer)

    version = await negotiate(mux, network_magic=42)

    assert version == 20
    # We actually sent a proposal.
    sent = cbor2.loads(bytes(writer.buffer)[8:])
    assert sent[0] == 0
