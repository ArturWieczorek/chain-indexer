"""A chain source: the thing that feeds the indexer with chain events.

Up to now we hand-fed synthetic blocks to the store. A real indexer instead
*follows* a chain, receiving a stream of two kinds of event:

- ``RollForward`` - here is the next block, apply it.
- ``RollBackward`` - back up to this point, the blocks after it are gone.

Those two events are exactly the chain-sync protocol's two messages. We capture
them as small dataclasses and hide the thing producing them behind a
``ChainSource`` interface. Chapter 08 implements the interface over Ogmios;
chapter 12 implements it a second time by speaking the wire protocol ourselves.
Because both satisfy the same interface, the sync loop in chapter 09 does not
care which one it is driving.

The interface is asynchronous (`async def`). Talking to a socket or a WebSocket
means waiting for bytes to arrive, and `async`/`await` lets us wait without
blocking. A `FakeSource` (also here) is a scripted, synchronous-feeling
implementation we use to test the sync loop without any network.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from chainidx.model import Block, Origin, Point


@dataclass(frozen=True)
class RollForward:
    """The next block on the chain."""

    block: Block


@dataclass(frozen=True)
class RollBackward:
    """Back up to ``point`` (or to the origin); later blocks are discarded."""

    point: Point | Origin


# One of the two things a source can hand us.
ChainEvent = RollForward | RollBackward


class SourceExhausted(Exception):
    """Raised by a finite source that has run out of events.

    A live source never raises this - it simply waits for the next block. It is
    used by the scripted ``FakeSource`` so a bounded sync knows when to stop.
    """


class ChainSource(Protocol):
    """The contract a chain source must satisfy."""

    async def find_intersection(self, points: Sequence[Point | Origin]) -> Point | Origin | None:
        """Agree with the source on the newest point we both know, or ``None``."""
        ...

    async def next_event(self) -> ChainEvent:
        """Return the next roll-forward or roll-backward event."""
        ...

    async def close(self) -> None:
        """Release the source's resources."""
        ...


class FakeSource:
    """A scripted, in-memory ``ChainSource`` for tests and demos."""

    def __init__(
        self,
        events: Iterable[ChainEvent],
        known_points: Iterable[Point | Origin] = (),
    ) -> None:
        self._events: list[ChainEvent] = list(events)
        self._index = 0
        self._known: set[Point | Origin] = set(known_points)

    async def find_intersection(self, points: Sequence[Point | Origin]) -> Point | Origin | None:
        for point in points:
            if point in self._known:
                return point
        return None

    async def next_event(self) -> ChainEvent:
        if self._index >= len(self._events):
            raise SourceExhausted
        event = self._events[self._index]
        self._index += 1
        return event

    async def close(self) -> None:
        return None
