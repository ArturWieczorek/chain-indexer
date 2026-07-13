"""The chain-sync mini-protocol: messages and parsing (the pure part).

Chain-sync is the conversation that lets a client follow the node's chain. It is
a small state machine driven by a handful of CBOR messages:

```
  us -> node:  [4, [point, ...]]   MsgFindIntersect   "do we share any of these?"
  node -> us:  [5, point, tip]     MsgIntersectFound
  node -> us:  [6, tip]            MsgIntersectNotFound

  us -> node:  [0]                 MsgRequestNext      "give me the next block"
  node -> us:  [1]                 MsgAwaitReply       "wait, nothing new yet"
  node -> us:  [2, block, tip]     MsgRollForward      "here is the next block"
  node -> us:  [3, point, tip]     MsgRollBackward     "back up to this point"
```

A point on the wire is ``[slot, hashBytes]``, or the empty array ``[]`` for the
origin. A block in ``MsgRollForward`` is the tag-24 CBOR wrapper we already know
how to decode (chapter 10).

This module is the pure message layer - building requests and parsing replies -
so it is fully unit-testable. The socket-driving ``NodeSource`` lives in
``node.py`` and uses these functions.
"""

from __future__ import annotations

from typing import Any

import cbor2

from chainidx.cbor_blocks import decode_block
from chainidx.model import Origin, Point
from chainidx.source import ChainEvent, RollBackward, RollForward


def encode_point(point: Point | Origin) -> list[Any]:
    """Encode one of our points for the wire ( ``[]`` for the origin)."""
    if isinstance(point, Origin):
        return []
    return [point.slot_no, bytes.fromhex(point.block_hash)]


def decode_point(encoded: list[Any]) -> Point | Origin:
    """Decode a wire point back to ours ( ``[]`` means origin)."""
    if not encoded:
        return Origin()
    slot, block_hash = encoded
    return Point(slot_no=slot, block_hash=block_hash.hex())


def find_intersect_message(points: list[Point | Origin]) -> list[Any]:
    """MsgFindIntersect: offer a list of points to intersect on."""
    return [4, [encode_point(p) for p in points]]


def request_next_message() -> list[Any]:
    """MsgRequestNext: ask for the next block."""
    return [0]


def parse_intersect_reply(message: list[Any]) -> Point | Origin | None:
    """Parse the reply to FindIntersect: the shared point, or ``None``."""
    tag = message[0]
    if tag == 5:  # MsgIntersectFound [5, point, tip]
        return decode_point(message[1])
    return None  # MsgIntersectNotFound [6, tip]


def parse_next_reply(message: list[Any]) -> ChainEvent | None:
    """Parse a reply to RequestNext.

    Returns a ``RollForward`` or ``RollBackward``, or ``None`` for
    ``MsgAwaitReply`` (the node has nothing new yet and will send later).
    """
    tag = message[0]
    if tag == 2:  # MsgRollForward [2, block, tip]
        return RollForward(block=decode_block(message[1]))
    if tag == 3:  # MsgRollBackward [3, point, tip]
        return RollBackward(point=decode_point(message[1]))
    return None  # MsgAwaitReply [1]


def encode(message: list[Any]) -> bytes:
    """Serialize a chain-sync message to CBOR bytes."""
    return cbor2.dumps(message)
