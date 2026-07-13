"""The sync loop: the follower that ties a source to the store.

This is the beating heart of the indexer, and it is short because every hard part
was solved in an earlier chapter. The follower does three things:

1. **Resume.** Offer the source our most recent points; it replies with the
   newest one we share (or the origin for a fresh database). That is where we
   pick up.
2. **Loop.** Pull events forever. A ``RollForward`` means index a block; a
   ``RollBackward`` means run the reorg engine.
3. **Keep score.** Count blocks applied and rolled back, so callers (and the
   dashboard, later) can see what happened.

The follower does not know or care whether the source is Ogmios or our own
wire-protocol client - it only sees ``ChainSource``. That is the whole reason we
defined the interface in chapter 08.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from chainidx.event import EventBus, describe_block
from chainidx.model import ORIGIN, Origin, Point
from chainidx.source import ChainSource, RollBackward, RollForward, SourceExhausted
from chainidx.store import Store


@dataclass
class FollowStats:
    """A running tally of what the follower has done."""

    events: int = 0
    applied: int = 0
    rolled_back: int = 0


class Follower:
    """Drives a ``ChainSource`` into a ``Store``."""

    def __init__(self, source: ChainSource, store: Store, bus: EventBus | None = None) -> None:
        self._source = source
        self._store = store
        self._bus = bus
        self.stats = FollowStats()

    async def resume(self) -> Point | Origin | None:
        """Agree with the source on where to resume, using our recent points."""
        candidates: list[Point | Origin] = [*self._store.recent_points(), ORIGIN]
        return await self._source.find_intersection(candidates)

    def apply(self, event: RollForward | RollBackward) -> None:
        """Apply one event to the store."""
        self.stats.events += 1
        if isinstance(event, RollForward):
            self._store.apply_block(event.block)
            self.stats.applied += 1
            if self._bus is not None:
                for domain_event in describe_block(event.block):
                    self._bus.publish(domain_event)
        else:
            # Translate the source's Origin marker to the store's "None = origin".
            target = None if isinstance(event.point, Origin) else event.point
            removed = self._store.rollback_to(target)
            self.stats.rolled_back += len(removed)
            if self._bus is not None:
                # A retraction event: the reorg story, streamed live.
                self._bus.publish({"type": "rollback", "removed": removed, "count": len(removed)})

    async def run(self, max_events: int | None = None) -> FollowStats:
        """Resume, then process events until exhausted or ``max_events`` reached.

        A live source never exhausts, so with ``max_events=None`` this follows the
        chain forever. Tests pass a bound (or a finite ``FakeSource``) so the loop
        terminates.
        """
        await self.resume()
        while max_events is None or self.stats.events < max_events:
            try:
                event = await self._source.next_event()
            except SourceExhausted:
                break
            self.apply(event)
        return self.stats


async def _main() -> None:  # pragma: no cover
    """Follow a live chain via Ogmios into a local database (``make run``)."""
    from chainidx.ogmios import OgmiosSource
    from chainidx.store import SqliteStore

    source = OgmiosSource()
    store = SqliteStore("chain.db")
    follower = Follower(source, store)
    try:
        while True:
            await follower.run(max_events=follower.stats.events + 100)
            tip = store.tip()
            height = tip.block_no if tip is not None else 0
            print(  # noqa: T201 - this is a CLI entry point
                f"tip height {height}, applied {follower.stats.applied}, "
                f"rolled back {follower.stats.rolled_back}"
            )
    finally:
        await source.close()
        store.close()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
