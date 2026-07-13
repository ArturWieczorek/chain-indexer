"""Integration test: follow a real chain via our own NodeSource (no Ogmios).

This is the proof that the from-scratch wire protocol fully replaces Ogmios: the
same Follower, pointed at a NodeSource, indexes the same chain. Marked
``integration`` and skipped unless ``CARDANO_NODE_SOCKET_PATH`` points at a live
node socket:

    source <(cardonnay control print-env -i 0)
    pytest -m integration
"""

import os
from pathlib import Path

import pytest

from chainidx.follow import Follower
from chainidx.node import NodeSource
from chainidx.store import SqliteStore

pytestmark = pytest.mark.integration


async def test_follow_a_real_chain_via_the_node_source() -> None:
    socket_path = os.environ.get("CARDANO_NODE_SOCKET_PATH")
    if not socket_path or not Path(socket_path).exists():
        pytest.skip("CARDANO_NODE_SOCKET_PATH is not set to a live node socket")

    store = SqliteStore()
    source = NodeSource(socket_path, network_magic=42)
    follower = Follower(source, store)
    try:
        stats = await follower.run(max_events=400)
    finally:
        await source.close()

    assert store.block_count() > 0
    assert stats.applied > 0
    tip = store.tip()
    assert tip is not None
    assert len(tip.point.block_hash) == 64
    # The from-scratch path indexes staking too: the cluster's pools appear.
    assert len(store.pools()) >= 1
    store.close()
