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

from chainidx.event import Event
from chainidx.patterns import EventFilter, event_filter_from_dict


@dataclass(frozen=True)
class WebhookSink:
    """A URL and the filter deciding which events reach it."""

    url: str
    event_filter: EventFilter

    def emit(self, event: Event) -> None:  # pragma: no cover - real HTTP
        _post(self.url, event)


def sink_from_dict(data: dict[str, Any]) -> WebhookSink:
    """Build a `WebhookSink` from one config entry (pure).

    The URL comes from ``url`` (the ``webhooks`` config shorthand) or ``target``
    (the general ``sinks`` config); the filter is built from the shared fields.
    """
    return WebhookSink(
        url=str(data.get("url") or data.get("target", "")),
        event_filter=event_filter_from_dict(data),
    )


def sinks_from_config(webhooks: tuple[dict[str, Any], ...]) -> list[WebhookSink]:
    """Build every configured webhook sink (pure)."""
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
