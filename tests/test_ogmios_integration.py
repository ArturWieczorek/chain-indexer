"""Integration test: drive a real Ogmios server.

Marked ``integration`` and skipped automatically when no Ogmios is reachable, so
the unit suite and CI stay offline. To run it for real, start a cardonnay cluster
and an Ogmios pointed at its node socket, then:

    pytest -m integration
"""

import contextlib

import pytest
import websockets

from chainidx.model import ORIGIN
from chainidx.ogmios import OgmiosSource
from chainidx.source import RollBackward, RollForward

pytestmark = pytest.mark.integration

_URL = "ws://127.0.0.1:1337"


async def _ogmios_is_up() -> bool:
    try:
        async with websockets.connect(_URL, open_timeout=2):
            return True
    except (OSError, websockets.WebSocketException):
        return False


async def test_follows_a_real_chain_from_the_origin() -> None:
    if not await _ogmios_is_up():
        pytest.skip("no Ogmios server on 127.0.0.1:1337")

    source = OgmiosSource(_URL)
    try:
        intersection = await source.find_intersection([ORIGIN])
        assert intersection == ORIGIN

        # The first reply after intersecting at the origin is a roll-back to the
        # origin; after that we roll forward through real blocks.
        first = await source.next_event()
        assert isinstance(first, RollBackward)

        seen_forward = 0
        for _ in range(50):
            event = await source.next_event()
            if isinstance(event, RollForward):
                seen_forward += 1
                assert len(event.block.block_hash) == 64
            if seen_forward >= 3:
                break
        assert seen_forward >= 1
    finally:
        with contextlib.suppress(Exception):
            await source.close()
