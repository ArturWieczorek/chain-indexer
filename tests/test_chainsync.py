"""Tests for the chain-sync message layer, using a real captured block."""

from pathlib import Path
from typing import cast

import cbor2

from chainidx.chainsync import (
    decode_point,
    encode,
    encode_point,
    find_intersect_message,
    parse_intersect_reply,
    parse_next_reply,
    request_next_message,
)
from chainidx.model import ORIGIN, Origin, Point
from chainidx.source import RollBackward, RollForward

FIXTURES = Path(__file__).parent / "fixtures"
_HASH = "aa" * 32
_REAL_BLOCK_HASH = "7058a7c4d6faf83b7f563ade99f38a30c021c8701aad16f6f51d6bb5865d8608"


def test_point_round_trips_including_origin() -> None:
    assert encode_point(ORIGIN) == []
    assert isinstance(decode_point([]), Origin)

    point = Point(slot_no=42, block_hash=_HASH)
    assert encode_point(point) == [42, bytes.fromhex(_HASH)]
    assert decode_point([42, bytes.fromhex(_HASH)]) == point


def test_message_builders() -> None:
    assert request_next_message() == [0]
    assert find_intersect_message([ORIGIN]) == [4, [[]]]
    assert find_intersect_message([Point(1, _HASH)]) == [4, [[1, bytes.fromhex(_HASH)]]]


def test_encode_serializes_to_cbor() -> None:
    import cbor2

    assert cbor2.loads(encode([0])) == [0]


def test_parse_intersect_reply() -> None:
    assert isinstance(parse_intersect_reply([5, [], "tip"]), Origin)
    assert parse_intersect_reply([5, [7, bytes.fromhex(_HASH)], "tip"]) == Point(7, _HASH)
    assert parse_intersect_reply([6, "tip"]) is None


def test_parse_next_reply_roll_forward_decodes_a_real_block() -> None:
    block_tag = cbor2.loads((FIXTURES / "node_block_txs.cbor").read_bytes())
    event = parse_next_reply([2, block_tag, "tip"])
    assert isinstance(event, RollForward)
    assert event.block.block_hash == _REAL_BLOCK_HASH


def test_parse_next_reply_roll_backward_and_await() -> None:
    backward = parse_next_reply([3, [9, bytes.fromhex(_HASH)], "tip"])
    assert isinstance(backward, RollBackward)
    assert cast(Point, backward.point) == Point(9, _HASH)

    to_origin = parse_next_reply([3, [], "tip"])
    assert isinstance(to_origin, RollBackward)
    assert isinstance(to_origin.point, Origin)

    # MsgAwaitReply carries no event.
    assert parse_next_reply([1]) is None
