"""Tests for the sync loop (Follower), driven by a scripted FakeSource."""

from chainidx.follow import Follower
from chainidx.model import ORIGIN, Block, Tx, TxIn, TxOut
from chainidx.source import ChainEvent, FakeSource, RollBackward, RollForward
from chainidx.store import SqliteStore


def blk(n: int, h: str, prev: str, txs: tuple[Tx, ...] = ()) -> Block:
    return Block(block_no=n, slot_no=n * 10, block_hash=h, prev_hash=prev, txs=txs)


async def test_follower_resumes_at_the_origin_for_a_fresh_store() -> None:
    store = SqliteStore()
    source = FakeSource([], known_points=[ORIGIN])
    follower = Follower(source, store)
    assert await follower.resume() == ORIGIN
    store.close()


async def test_follower_indexes_a_forward_stream() -> None:
    store = SqliteStore()
    events: list[ChainEvent] = [
        RollBackward(ORIGIN),
        RollForward(blk(1, "b1", "genesis", (Tx("t1", outputs=(TxOut("alice", 5_000_000),)),))),
        RollForward(blk(2, "b2", "b1")),
    ]
    follower = Follower(FakeSource(events, known_points=[ORIGIN]), store)

    stats = await follower.run()

    assert store.block_count() == 2
    assert store.balance("alice") == 5_000_000
    assert stats.applied == 2
    assert stats.rolled_back == 0
    assert stats.events == 3
    store.close()


async def test_follower_handles_a_reorg_through_the_loop() -> None:
    store = SqliteStore()
    fund = Tx("t1", outputs=(TxOut("alice", 10_000_000),))
    spend = Tx("t2", inputs=(TxIn("t1", 0),), outputs=(TxOut("bob", 10_000_000),))
    events: list[ChainEvent] = [
        RollBackward(ORIGIN),
        RollForward(blk(1, "b1", "genesis", (fund,))),
        RollForward(blk(2, "b2", "b1", (spend,))),
        RollForward(blk(3, "b3", "b2")),
        # The chain reorgs back to b1 and takes a different branch.
        RollBackward(blk(1, "b1", "genesis").point),
        RollForward(blk(2, "b2x", "b1")),
        RollForward(blk(3, "b3x", "b2x")),
    ]
    follower = Follower(FakeSource(events, known_points=[ORIGIN]), store)

    stats = await follower.run()

    assert store.block_count() == 3
    tip = store.tip()
    assert tip is not None
    assert tip.point.block_hash == "b3x"
    # The reorg undid the spend, so alice is whole again and bob is gone.
    assert store.balance("alice") == 10_000_000
    assert store.balance("bob") == 0
    assert stats.applied == 5
    assert stats.rolled_back == 2
    store.close()


async def test_follower_respects_max_events() -> None:
    store = SqliteStore()
    forward: list[ChainEvent] = [RollBackward(ORIGIN), *(RollForward(blk(i, f"b{i}", "p")) for i in range(1, 6))]
    follower = Follower(FakeSource(forward, known_points=[ORIGIN]), store)

    stats = await follower.run(max_events=3)

    assert stats.events == 3
    store.close()
