"""Integration test: perform the real handshake against a live node socket.

Marked ``integration`` and skipped unless ``CARDANO_NODE_SOCKET_PATH`` points at
a live node socket. To run it, source a cardonnay cluster's env first:

    source <(cardonnay control print-env -i 0)
    pytest -m integration
"""

import asyncio
import os
from pathlib import Path

import pytest

from chainidx.handshake import negotiate
from chainidx.mux import MuxConnection

pytestmark = pytest.mark.integration

# cardonnay's local clusters use network magic 42.
_MAGIC = 42


async def test_handshake_with_a_real_node() -> None:
    socket_path = os.environ.get("CARDANO_NODE_SOCKET_PATH")
    if not socket_path or not Path(socket_path).exists():
        pytest.skip("CARDANO_NODE_SOCKET_PATH is not set to a live node socket")

    reader, writer = await asyncio.open_unix_connection(socket_path)
    try:
        version = await negotiate(MuxConnection(reader, writer), _MAGIC)
        # The node accepts a modern node-to-client version.
        assert version >= 9
    finally:
        writer.close()
