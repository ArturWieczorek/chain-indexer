"""Tests for the in-memory chain: extending it, detecting forks, rolling back."""

import pytest

from chainidx.chain import Chain, ForkError
from chainidx.model import Block


def block(block_no: int, block_hash: str, prev_hash: str) -> Block:
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=(),
    )


def build(*hashes_and_parents: tuple[str, str]) -> Chain:
    """Build a chain from (hash, prev_hash) pairs, oldest first."""
    chain = Chain()
    for i, (h, prev) in enumerate(hashes_and_parents, start=1):
        chain.add_block(block(i, h, prev))
    return chain


def test_a_fresh_chain_is_empty() -> None:
    chain = Chain()
    assert len(chain) == 0
    assert chain.tip is None
    assert chain.tip_block is None


def test_a_chain_can_be_built_from_initial_blocks() -> None:
    chain = Chain([block(1, "b1", "genesis"), block(2, "b2", "b1")])
    assert len(chain) == 2
    assert [b.block_hash for b in chain.blocks()] == ["b1", "b2"]


def test_add_block_extends_the_chain() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"), ("b3", "b2"))
    assert len(chain) == 3
    assert chain.tip_block is not None
    assert chain.tip_block.block_hash == "b3"
    assert chain.tip == block(3, "b3", "b2").point


def test_a_block_that_does_not_link_onto_the_tip_is_rejected() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"))
    stray = block(3, "b3", "does_not_match_b2")
    with pytest.raises(ForkError):
        chain.add_block(stray)
    # The chain is unchanged after a rejected block.
    assert len(chain) == 2
    assert chain.tip_block is not None
    assert chain.tip_block.block_hash == "b2"


def test_has_point_knows_which_points_are_on_the_chain() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"))
    assert chain.has_point(block(1, "b1", "genesis").point) is True
    assert chain.has_point(block(2, "b2", "b1").point) is True
    assert chain.has_point(block(9, "nope", "b2").point) is False


def test_rollback_to_a_point_drops_the_blocks_after_it() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"), ("b3", "b2"), ("b4", "b3"))
    target = block(2, "b2", "b1").point

    removed = chain.rollback_to(target)

    assert chain.tip == target
    assert len(chain) == 2
    # Removed blocks come back newest-first, which is the safe deletion order
    # (leaf-first) we will need when we delete their rows in chapter 05.
    assert [b.block_hash for b in removed] == ["b4", "b3"]


def test_rollback_to_none_empties_the_chain() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"))
    removed = chain.rollback_to(None)
    assert len(chain) == 0
    assert chain.tip is None
    assert [b.block_hash for b in removed] == ["b2", "b1"]


def test_rollback_to_an_unknown_point_is_an_error() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"))
    with pytest.raises(ValueError, match="unknown point"):
        chain.rollback_to(block(9, "ghost", "b2").point)


def test_points_lists_the_chain_newest_first() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"), ("b3", "b2"))
    assert [p.block_hash for p in chain.points()] == ["b3", "b2", "b1"]


def test_find_intersection_returns_the_newest_shared_point() -> None:
    chain = build(("b1", "genesis"), ("b2", "b1"), ("b3", "b2"))
    # Candidates are offered newest-first, exactly as the chain-sync protocol
    # will offer them later. b5 and b4 are unknown; b2 is the newest we share.
    candidates = [
        block(5, "b5", "b4").point,
        block(4, "b4", "b3x").point,
        block(2, "b2", "b1").point,
        block(1, "b1", "genesis").point,
    ]
    assert chain.find_intersection(candidates) == block(2, "b2", "b1").point


def test_find_intersection_returns_none_when_nothing_is_shared() -> None:
    chain = build(("b1", "genesis"))
    candidates = [block(9, "x", "y").point]
    assert chain.find_intersection(candidates) is None


def test_switching_to_a_fork_end_to_end() -> None:
    # Our chain: b1 <- b2 <- b3.
    chain = build(("b1", "genesis"), ("b2", "b1"), ("b3", "b2"))

    # A competing branch appears that diverges after b1: b2x <- b3x <- b4x.
    fork = [block(2, "b2x", "b1"), block(3, "b3x", "b2x"), block(4, "b4x", "b3x")]

    # Find where the branches diverge (the newest point the fork shares with us),
    # roll back to it, then apply the fork's blocks.
    intersection = chain.find_intersection([b.point for b in reversed(fork)] + [chain.points()[-1]])
    assert intersection == block(1, "b1", "genesis").point

    chain.rollback_to(intersection)
    for b in fork:
        chain.add_block(b)

    assert chain.tip_block is not None
    assert chain.tip_block.block_hash == "b4x"
    assert len(chain) == 4
