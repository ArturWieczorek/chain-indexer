"""Integration test: force a real node to roll us back, and verify we recover.

A true adversarial fork needs partitioned block producers, which a healthy local
cluster does not give us. But we can make the *real node* send a genuine
``RollBackward`` on demand: reconnect and ask it to resume from an earlier point.
The node replies by rolling us back to there. We apply that rollback to a store
that is already ahead, then re-index forward, and check we land on exactly the
same tip - proving the rollback path against a real node-issued message.

Marked ``integration`` and skipped unless ``CARDANO_NODE_SOCKET_PATH`` is set:

    source <(cardonnay control print-env -i 0)
    pytest -m integration
"""

import os
from pathlib import Path

import pytest

from chainidx.follow import Follower
from chainidx.node import NodeSource
from chainidx.source import RollBackward
from chainidx.store import SqliteStore

pytestmark = pytest.mark.integration

_MAGIC = 42


async def test_forced_rollback_and_recovery() -> None:
    socket_path = os.environ.get("CARDANO_NODE_SOCKET_PATH")
    if not socket_path or not Path(socket_path).exists():
        pytest.skip("CARDANO_NODE_SOCKET_PATH is not set to a live node socket")

    store = SqliteStore()

    # 1. Follow the real chain to a tip.
    source = NodeSource(socket_path, _MAGIC)
    await Follower(source, store).run(max_events=200)
    await source.close()

    original_tip = store.tip()
    assert original_tip is not None
    points = store.recent_points(limit=20)
    if len(points) < 12:
        pytest.skip("not enough blocks to force a meaningful rollback")
    target = points[10]  # about ten blocks back

    # 2. Reconnect and ask the node to resume from that earlier point.
    source = NodeSource(socket_path, _MAGIC)
    follower = Follower(source, store)
    intersection = await source.find_intersection([target])
    assert intersection == target

    # 3. The node's first message is a real RollBackward to that point.
    first = await source.next_event()
    assert isinstance(first, RollBackward)
    follower.apply(first)
    rolled_tip = store.tip()
    assert rolled_tip is not None
    assert rolled_tip.block_no < original_tip.block_no
    assert follower.stats.rolled_back > 0

    # 4. Re-index forward and confirm we return to the exact same tip.
    for _ in range(500):
        current = store.tip()
        if current is not None and current.block_no >= original_tip.block_no:
            break
        follower.apply(await source.next_event())
    await source.close()

    recovered_tip = store.tip()
    assert recovered_tip is not None
    assert recovered_tip.point.block_hash == original_tip.point.block_hash
    store.close()
