"""Webhook sinks: push filtered events to HTTP endpoints (chapter 69).

This is adder's "output" idea. A `WebhookSink` subscribes to the event bus (chapter
16), keeps only the events matching an `EventFilter` (chapter 68), and POSTs each
survivor as JSON to a configured URL. Rollback events flow through too, so a
consumer can react to a reorg - the differentiator over a naive block notifier.

Configuration lives in the JSON config as a `webhooks` list, each entry a URL plus
the filter fields:

    "webhooks": [
      {"url": "https://example/hook", "addresses": ["addr_test1..."]},
      {"url": "https://example/reorgs", "types": ["rollback"]}
    ]

Building a sink from that config, and encoding the payload, are pure and tested. The
actual HTTP POST and the subscribe-forever loop need a network and a live loop, so
they are marked ``# pragma: no cover`` like the other integration code (``offchain``,
the mini-protocol clients).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from chainidx.event import Event, EventBus
from chainidx.patterns import EventFilter, parse_pattern


@dataclass(frozen=True)
class WebhookSink:
    """A URL and the filter deciding which events reach it."""

    url: str
    event_filter: EventFilter


def _normalise_address(text: str) -> str:
    """A configured address as the raw hex the events carry (bech32 is decoded)."""
    parsed = parse_pattern(text)
    return parsed.value if parsed.kind == "address" else text


def sink_from_dict(data: dict[str, Any]) -> WebhookSink:
    """Build a `WebhookSink` from one config entry (pure).

    Addresses are decoded from bech32 to the hex the `transaction` events carry;
    policies and assets are lower-cased to match. A missing field does not filter.
    """
    event_filter = EventFilter(
        types=frozenset(data.get("types", ())),
        addresses=frozenset(_normalise_address(a) for a in data.get("addresses", ())),
        policies=frozenset(p.lower() for p in data.get("policies", ())),
        assets=frozenset(a.lower() for a in data.get("assets", ())),
    )
    return WebhookSink(url=str(data["url"]), event_filter=event_filter)


def sinks_from_config(webhooks: tuple[dict[str, Any], ...]) -> list[WebhookSink]:
    """Build every configured sink (pure)."""
    return [sink_from_dict(entry) for entry in webhooks]


def encode_payload(event: Event) -> bytes:
    """The JSON body POSTed for an event (pure)."""
    return json.dumps(event).encode("utf-8")


def _post(url: str, event: Event) -> None:  # pragma: no cover - real HTTP
    """POST one event, best-effort: a failing webhook must not stall the indexer."""
    import contextlib
    import urllib.request

    request = urllib.request.Request(
        url,
        data=encode_payload(event),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with contextlib.suppress(Exception):
        urllib.request.urlopen(request, timeout=5).close()


async def run_sink(bus: EventBus, sink: WebhookSink) -> None:  # pragma: no cover - live loop
    """Subscribe to the bus and POST every matching event to the sink's URL."""
    queue = bus.subscribe()
    while True:
        event = await queue.get()
        if sink.event_filter.matches(event):
            _post(sink.url, event)
