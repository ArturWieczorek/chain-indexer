"""Off-chain metadata: fetch a pool's registered JSON and read its name/ticker.

A pool registration only puts a metadata *anchor* on-chain (a URL and a hash,
chapter 50). The human-facing fields - name, ticker, homepage, description - live
in a JSON document at that URL, off-chain. This module reads them.

The parsing is pure and unit-tested. The actual HTTP fetch (`fetch_pool_metadata`)
touches the network, so it is excluded from coverage and only runs when metadata
fetching is switched on (the ``CHAINIDX_FETCH_METADATA`` environment variable),
wired in by the server. Keeping the fetch opt-in means the default, offline
behaviour is unchanged and tests never reach for the network.
"""

from __future__ import annotations

import json
from typing import Any

# The CIP-6 pool metadata fields we surface.
_POOL_FIELDS = ("name", "ticker", "homepage", "description")


def parse_pool_metadata(raw: bytes) -> dict[str, Any] | None:
    """Read the known fields out of pool metadata JSON, or ``None`` if unusable."""
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    fields = {key: data[key] for key in _POOL_FIELDS if key in data}
    return fields or None


def fetch_pool_metadata(
    url: str, timeout: float = 3.0
) -> dict[str, Any] | None:  # pragma: no cover
    """Fetch and parse a pool's off-chain metadata; ``None`` on any error."""
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read(64_000)  # metadata is tiny; cap the read
    except Exception:
        return None
    return parse_pool_metadata(raw)
