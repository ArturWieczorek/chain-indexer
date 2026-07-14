"""Integration test: read ledger state from a live node via local-state-query.

Marked ``integration`` and skipped unless ``CARDANO_NODE_SOCKET_PATH`` points at a
live node socket:

    source <(cardonnay control print-env -i 0)
    pytest -m integration
"""

import os
from pathlib import Path

import pytest

from chainidx.localstate import LocalStateClient

pytestmark = pytest.mark.integration


async def test_read_ledger_state_from_a_real_node() -> None:
    socket_path = os.environ.get("CARDANO_NODE_SOCKET_PATH")
    if not socket_path or not Path(socket_path).exists():
        pytest.skip("CARDANO_NODE_SOCKET_PATH is not set to a live node socket")

    snapshot = await LocalStateClient(socket_path, network_magic=42).snapshot()

    assert snapshot.epoch >= 0
    assert snapshot.system_start.startswith("20")
    assert snapshot.protocol_params["min_fee_a"] >= 0
    # The cardonnay cluster runs three pools; their stake shares are fractions.
    assert len(snapshot.stake_pools) == 3
    assert len(snapshot.stake_distribution) >= 1
    assert all(0.0 <= p.stake <= 1.0 for p in snapshot.stake_distribution)
