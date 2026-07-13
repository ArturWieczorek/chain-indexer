"""Tests for the event bus and block-to-events mapping."""

from chainidx.event import EventBus, describe_block
from chainidx.follow import Follower
from chainidx.model import (
    ORIGIN,
    Block,
    DRepRegistration,
    GovActionProposal,
    GovVote,
    PoolRegistration,
    StakeDelegation,
    Tx,
    TxOut,
)
from chainidx.source import ChainEvent, FakeSource, RollBackward, RollForward
from chainidx.store import SqliteStore


def rich_block(block_no: int, block_hash: str, prev_hash: str) -> Block:
    return Block(
        block_no=block_no,
        slot_no=block_no * 10,
        block_hash=block_hash,
        prev_hash=prev_hash,
        txs=(
            Tx(
                "tx1",
                outputs=(TxOut("alice", 1_000_000),),
                certificates=(
                    PoolRegistration("pool1", 1000, 0.03, "stake_r"),
                    StakeDelegation("stake_alice", "pool1"),
                    DRepRegistration("drep1", 500),
                ),
                proposals=(GovActionProposal("gov1", "InfoAction", 0, "stake_r"),),
                votes=(GovVote("gov1", "DRep", "drep1", "Yes"),),
            ),
        ),
    )


def test_describe_block_emits_one_event_per_thing() -> None:
    events = describe_block(rich_block(1, "b1", "genesis"))
    types = [e["type"] for e in events]
    assert types[0] == "block"
    assert set(types) == {
        "block",
        "pool_registered",
        "stake_delegated",
        "drep_registered",
        "gov_action_proposed",
        "vote_cast",
    }


async def test_event_bus_delivers_to_subscribers() -> None:
    bus = EventBus()
    queue = bus.subscribe()

    bus.publish({"type": "block", "block_no": 1})
    bus.publish({"type": "rollback", "count": 2})

    assert (await queue.get())["block_no"] == 1
    assert (await queue.get())["count"] == 2

    # After unsubscribing, no more events arrive.
    bus.unsubscribe(queue)
    bus.publish({"type": "block", "block_no": 2})
    assert queue.empty()


async def test_follower_publishes_events_including_a_rollback() -> None:
    bus = EventBus()
    queue = bus.subscribe()
    store = SqliteStore()
    events: list[ChainEvent] = [
        RollForward(rich_block(1, "b1", "genesis")),
        RollForward(Block(2, 20, "b2", "b1", txs=())),
        RollBackward(rich_block(1, "b1", "genesis").point),
    ]
    follower = Follower(FakeSource(events, known_points=[ORIGIN]), store, bus=bus)

    await follower.run()

    collected = []
    while not queue.empty():
        collected.append(queue.get_nowait())
    types = {e["type"] for e in collected}
    assert "block" in types
    assert "pool_registered" in types
    assert "vote_cast" in types
    assert "rollback" in types
    store.close()
