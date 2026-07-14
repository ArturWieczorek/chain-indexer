"""Integration test: read delegation + rewards from a live node.

Marked ``integration`` and skipped unless ``CARDANO_NODE_SOCKET_PATH`` is set.
"""

import os
from pathlib import Path

import pytest

from chainidx.localstate import LocalStateClient

pytestmark = pytest.mark.integration

# A stake credential registered on the cardonnay cluster (a pool owner).
_CREDENTIAL = "e9546949f50285fd15493fe5ba3ffc8bac4aef1c34f5a294d66be825"


async def test_account_states_from_a_real_node() -> None:
    socket_path = os.environ.get("CARDANO_NODE_SOCKET_PATH")
    if not socket_path or not Path(socket_path).exists():
        pytest.skip("CARDANO_NODE_SOCKET_PATH is not set to a live node socket")

    states = await LocalStateClient(socket_path, network_magic=42).account_states([_CREDENTIAL])

    assert _CREDENTIAL in states
    account = states[_CREDENTIAL]
    assert account.reward >= 0
    # A pool owner delegates to a pool.
    assert account.delegated_pool is None or len(account.delegated_pool) == 56
