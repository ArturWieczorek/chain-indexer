"""Integration test: follow a real chain via Ogmios into a real SQLite store.

Marked ``integration`` and skipped when no Ogmios is reachable. To run it:

    pytest -m integration
"""

import pytest
import websockets

from chainidx.follow import Follower
from chainidx.ogmios import OgmiosSource
from chainidx.store import SqliteStore

pytestmark = pytest.mark.integration

_URL = "ws://127.0.0.1:1337"


async def _ogmios_is_up() -> bool:
    try:
        async with websockets.connect(_URL, open_timeout=2):
            return True
    except (OSError, websockets.WebSocketException):
        return False


async def test_follows_a_real_chain_into_the_store() -> None:
    if not await _ogmios_is_up():
        pytest.skip("no Ogmios server on 127.0.0.1:1337")

    store = SqliteStore()
    source = OgmiosSource(_URL)
    follower = Follower(source, store)
    try:
        stats = await follower.run(max_events=400)
    finally:
        await source.close()

    # We indexed real blocks and at least some transactions with outputs.
    assert store.block_count() > 0
    assert stats.applied > 0
    tip = store.tip()
    assert tip is not None
    assert len(tip.point.block_hash) == 64
    store.close()
