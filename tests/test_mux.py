"""Tests for the mux framing and message reassembly, using in-memory streams."""

import asyncio
import struct

import cbor2

from chainidx.mux import MuxConnection, pack_header, unpack_header


class FakeWriter:
    """Captures the bytes written to it."""

    def __init__(self) -> None:
        self.buffer = bytearray()

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None


def frame(protocol: int, payload: bytes) -> bytes:
    return pack_header(protocol, len(payload)) + payload


def reader_with(*chunks: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    for chunk in chunks:
        reader.feed_data(chunk)
    reader.feed_eof()
    return reader


def test_header_round_trips() -> None:
    protocol, length, from_responder = unpack_header(pack_header(5, 1234))
    assert protocol == 5
    assert length == 1234
    assert from_responder is False


def test_header_detects_a_responder_frame() -> None:
    # A responder sets the top bit of the protocol field.
    raw = struct.pack(">IHH", 0, 5 | 0x8000, 10)
    protocol, length, from_responder = unpack_header(raw)
    assert protocol == 5
    assert length == 10
    assert from_responder is True


async def test_send_frames_the_payload() -> None:
    writer = FakeWriter()
    mux = MuxConnection(asyncio.StreamReader(), writer)
    await mux.send(0, b"hello")
    assert bytes(writer.buffer) == frame(0, b"hello")


async def test_receive_returns_one_message() -> None:
    payload = cbor2.dumps([1, 2, 3])
    mux = MuxConnection(reader_with(frame(0, payload)), FakeWriter())
    assert await mux.receive(0) == [1, 2, 3]


async def test_receive_reassembles_a_message_split_across_frames() -> None:
    payload = cbor2.dumps(["a", "message", "in", "pieces"])
    mux = MuxConnection(reader_with(frame(0, payload[:3]), frame(0, payload[3:])), FakeWriter())
    assert await mux.receive(0) == ["a", "message", "in", "pieces"]


async def test_receive_splits_two_messages_in_one_frame() -> None:
    payload = cbor2.dumps([1]) + cbor2.dumps([2])
    mux = MuxConnection(reader_with(frame(0, payload)), FakeWriter())
    assert await mux.receive(0) == [1]
    # The second message was left buffered; no further frame is needed.
    assert await mux.receive(0) == [2]
