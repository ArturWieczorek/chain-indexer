"""An in-memory chain, and the fork logic every indexer needs.

This module knows nothing about databases or networks. It is the "chain view"
from chapter 00's two-copies-of-reality picture: a cheap, in-memory record of
which blocks we currently believe are on the chain, and the operations that let
us extend it, notice a fork, and rewind it.

The three operations that matter:

- ``add_block`` extends the chain, and *refuses* a block that does not build on
  the current tip. That refusal is fork detection in its simplest form.
- ``find_intersection`` answers "given these candidate points, what is the newest
  one I already have?" - the exact question the chain-sync protocol asks when two
  chains need to agree on where they diverge.
- ``rollback_to`` rewinds the chain to a point and hands back the blocks it
  removed, newest-first. That order matters later: it is the safe order to delete
  the corresponding database rows.
"""

from __future__ import annotations

from collections.abc import Iterable

from chainidx.model import Block, Point


class ForkError(Exception):
    """Raised when a block does not build on the current tip.

    It means the incoming block belongs to a different branch, so the caller must
    first roll back to the point where the branches share history and only then
    apply the new branch.
    """


class Chain:
    """An ordered, in-memory sequence of blocks (oldest first)."""

    def __init__(self, blocks: Iterable[Block] = ()) -> None:
        self._blocks: list[Block] = []
        self._points: set[Point] = set()
        for b in blocks:
            self.add_block(b)

    def __len__(self) -> int:
        return len(self._blocks)

    @property
    def tip_block(self) -> Block | None:
        """The newest block, or ``None`` if the chain is empty."""
        return self._blocks[-1] if self._blocks else None

    @property
    def tip(self) -> Point | None:
        """The point of the newest block, or ``None`` if the chain is empty."""
        tip = self.tip_block
        return tip.point if tip is not None else None

    def blocks(self) -> tuple[Block, ...]:
        """A snapshot of the chain, oldest first."""
        return tuple(self._blocks)

    def add_block(self, block: Block) -> None:
        """Extend the chain with ``block``, or raise ``ForkError``.

        The first block of an empty chain is accepted as-is (we do not track the
        genesis block it builds on). Every later block must link onto the current
        tip.
        """
        tip = self.tip_block
        if tip is not None and not block.links_onto(tip):
            raise ForkError(
                f"block {block.block_hash!r} (prev={block.prev_hash!r}) "
                f"does not build on tip {tip.block_hash!r}"
            )
        self._blocks.append(block)
        self._points.add(block.point)

    def has_point(self, point: Point) -> bool:
        """True if ``point`` names a block currently on this chain."""
        return point in self._points

    def points(self) -> list[Point]:
        """Every point on the chain, newest first.

        Chain-sync offers points newest-first when looking for an intersection,
        so this is the order we produce them in.
        """
        return [b.point for b in reversed(self._blocks)]

    def find_intersection(self, candidates: Iterable[Point]) -> Point | None:
        """Return the first candidate that is on this chain, or ``None``.

        Callers offer candidates newest-first, so the first match is the newest
        shared point - the place two chains diverge.
        """
        for point in candidates:
            if point in self._points:
                return point
        return None

    def rollback_to(self, point: Point | None) -> list[Block]:
        """Rewind the chain to ``point`` and return the removed blocks.

        ``point`` of ``None`` means "back to the origin" - remove everything.
        The removed blocks are returned newest-first, which is the safe order to
        undo their effects (a later block may depend on an earlier one, so we
        peel from the tip inwards).
        """
        if point is None:
            removed = list(reversed(self._blocks))
            self._blocks = []
            self._points = set()
            return removed

        if not self.has_point(point):
            raise ValueError(f"cannot roll back to unknown point: {point!r}")

        # Keep every block up to and including the one at `point`; the rest are
        # removed and returned newest-first.
        cut = next(i for i, b in enumerate(self._blocks) if b.point == point)
        removed = list(reversed(self._blocks[cut + 1 :]))
        self._blocks = self._blocks[: cut + 1]
        self._points = {b.point for b in self._blocks}
        return removed
