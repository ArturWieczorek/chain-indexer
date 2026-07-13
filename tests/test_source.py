"""Tests for the chain source abstraction and the scripted FakeSource."""

import pytest

from chainidx.model import ORIGIN, Block, Origin, Point
from chainidx.source import (
    FakeSource,
    RollBackward,
    RollForward,
    SourceExhausted,
)


def a_block(h: str) -> Block:
    return Block(block_no=1, slot_no=10, block_hash=h, prev_hash="genesis", txs=())


def test_origin_is_a_value_like_singleton() -> None:
    assert Origin() == ORIGIN
    assert {Origin(), ORIGIN} == {ORIGIN}


async def test_fake_source_yields_scripted_events_then_stops() -> None:
    events = [RollForward(a_block("b1")), RollBackward(ORIGIN)]
    source = FakeSource(events)

    first = await source.next_event()
    assert isinstance(first, RollForward)
    assert first.block.block_hash == "b1"

    second = await source.next_event()
    assert isinstance(second, RollBackward)
    assert second.point == ORIGIN

    with pytest.raises(SourceExhausted):
        await source.next_event()

    await source.close()


async def test_fake_source_find_intersection_returns_the_first_known_point() -> None:
    p1 = Point(slot_no=10, block_hash="b1")
    p2 = Point(slot_no=20, block_hash="b2")
    source = FakeSource([], known_points=[p1])

    assert await source.find_intersection([p2, p1]) == p1
    assert await source.find_intersection([p2]) is None
    # The origin can be a known point too.
    origin_source = FakeSource([], known_points=[ORIGIN])
    assert await origin_source.find_intersection([ORIGIN]) == ORIGIN
