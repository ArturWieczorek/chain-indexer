"""The Ouroboros multiplexer (mux): framing for the node's socket.

A cardano-node exposes several mini-protocols over a single connection
(handshake, chain-sync, and others). To share one socket among them, every
message is wrapped in an 8-byte **mux header** that says which mini-protocol it
belongs to and how long it is. This module reads and writes that framing.

The header is 8 bytes, big-endian:

```
   0               4       6       8   (byte offset)
   +---------------+-------+-------+
   | transmit time | proto | len   |
   +---------------+-------+-------+
     uint32          uint16  uint16
```

- **transmit time**: the low 32 bits of a microsecond clock. The node uses it for
  its own flow accounting; the value we send does not affect correctness.
- **proto**: the mini-protocol number. Its top bit is the *mode*: 0 for messages
  from the initiator (us), 1 for messages from the responder (the node). So when
  we read a header, we mask the top bit off to recover the protocol number.
- **len**: the length of the payload that follows this header.

A single mini-protocol message can be larger than one 65535-byte frame, so it may
be split across several. The ``MuxConnection`` here reassembles them: it keeps a
buffer per protocol and hands back one complete CBOR message at a time.
"""

from __future__ import annotations

import asyncio
import io
import struct
from typing import Any, Protocol

import cbor2

# Node-to-client mini-protocol numbers.
PROTOCOL_HANDSHAKE = 0
PROTOCOL_CHAIN_SYNC = 5
PROTOCOL_LOCAL_TX_SUBMISSION = 6
PROTOCOL_LOCAL_STATE_QUERY = 7
PROTOCOL_LOCAL_TX_MONITOR = 9

_RESPONDER_FLAG = 0x8000
_HEADER = struct.Struct(">IHH")


class Writer(Protocol):
    """The slice of an asyncio StreamWriter we use."""

    def write(self, data: bytes) -> None: ...
    async def drain(self) -> None: ...


def pack_header(protocol: int, length: int, timestamp: int = 0) -> bytes:
    """Build an 8-byte mux header for a message we are sending (mode 0)."""
    return _HEADER.pack(timestamp & 0xFFFFFFFF, protocol, length)


def unpack_header(header: bytes) -> tuple[int, int, bool]:
    """Read a mux header, returning (protocol, length, from_responder)."""
    _timestamp, raw_protocol, length = _HEADER.unpack(header)
    from_responder = bool(raw_protocol & _RESPONDER_FLAG)
    protocol = raw_protocol & ~_RESPONDER_FLAG
    return protocol, length, from_responder


class MuxConnection:
    """Message-oriented framing over a byte stream.

    ``send`` frames one payload; ``receive`` returns one complete CBOR message,
    reassembling across frames as needed. We only ever run one mini-protocol at a
    time, but the per-protocol buffer keeps us honest if a frame arrives early.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: Writer) -> None:
        self._reader = reader
        self._writer = writer
        self._buffers: dict[int, bytes] = {}

    async def send(self, protocol: int, payload: bytes) -> None:
        self._writer.write(pack_header(protocol, len(payload)) + payload)
        await self._writer.drain()

    async def _read_frame(self) -> tuple[int, bytes]:
        protocol, length, _ = unpack_header(await self._reader.readexactly(8))
        return protocol, await self._reader.readexactly(length)

    async def receive(self, protocol: int) -> Any:
        """Return the next complete CBOR message for ``protocol``."""
        buffer = self._buffers.get(protocol, b"")
        while True:
            reader = io.BytesIO(buffer)
            try:
                message = cbor2.CBORDecoder(reader).decode()
            except cbor2.CBORDecodeError:
                # Not enough bytes yet - pull another frame and try again.
                frame_protocol, payload = await self._read_frame()
                if frame_protocol == protocol:
                    buffer += payload
                else:  # pragma: no cover - single-protocol use never hits this
                    self._buffers[frame_protocol] = self._buffers.get(frame_protocol, b"") + payload
                continue
            self._buffers[protocol] = buffer[reader.tell() :]
            return message
