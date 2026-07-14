"""Event sinks: the places filtered events can go (chapter 76).

Chapter 69 pushed events to webhooks. But the event bus (chapter 16) is built for
many consumers, so this generalises "an output" into a **sink**: anything with an
``EventFilter`` and an ``emit(event)``. Three ship in the box, all standard-library
only:

- :class:`~chainidx.webhook.WebhookSink` - POST each event to a URL (chapter 69);
- :class:`LogSink` - print each event to the console (adder's log output);
- :class:`FileSink` - append each event as a line of JSON to a file (an audit trail
  you can replay or ``grep`` offline).

Configuration is one ``sinks`` list, each entry ``{type, target, ...filters}``:

    "sinks": [
      {"type": "log",  "types": ["rollback"]},
      {"type": "file", "target": "events.jsonl", "policies": ["<policyid>"]},
      {"type": "webhook", "target": "https://example/hook", "addresses": ["addr_test1..."]}
    ]

``type`` selects the sink (default ``webhook``); ``target`` is the URL or file path
(a log sink needs none); the filter fields are the same as everywhere else
(``types`` / ``addresses`` / ``policies`` / ``assets``). The older ``webhooks``
list still works as shorthand for webhook sinks.

The ``emit`` of the log and file sinks is plain and unit-tested; only the
subscribe-forever :func:`run_sink` loop needs a live event loop, so it is the one
part marked ``# pragma: no cover`` (as with the other integration code).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from chainidx.event import Event, EventBus
from chainidx.patterns import EventFilter, event_filter_from_dict
from chainidx.webhook import sink_from_dict as _webhook_from_dict


class Sink(Protocol):
    """Anything the runner can drive: a filter, and somewhere to send matches."""

    @property
    def event_filter(self) -> EventFilter: ...

    def emit(self, event: Event) -> None: ...


@dataclass(frozen=True)
class LogSink:
    """Print each matching event to the console as one line of JSON."""

    event_filter: EventFilter

    def emit(self, event: Event) -> None:
        print(json.dumps(event), flush=True)


@dataclass(frozen=True)
class FileSink:
    """Append each matching event to a file, one JSON object per line (JSONL)."""

    event_filter: EventFilter
    path: str

    def emit(self, event: Event) -> None:
        with Path(self.path).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")


def build_sink(data: dict[str, Any]) -> Sink:
    """Build one sink from a config entry, dispatching on ``type`` (pure)."""
    kind = str(data.get("type", "webhook"))
    if kind == "log":
        return LogSink(event_filter_from_dict(data))
    if kind == "file":
        return FileSink(event_filter_from_dict(data), str(data["target"]))
    if kind == "webhook":
        return _webhook_from_dict(data)
    raise ValueError(f"unknown sink type: {kind!r}")


def build_sinks(entries: tuple[dict[str, Any], ...]) -> list[Sink]:
    """Build every sink in a ``sinks`` config list (pure)."""
    return [build_sink(entry) for entry in entries]


async def run_sink(bus: EventBus, sink: Sink) -> None:  # pragma: no cover - live loop
    """Subscribe to the bus and emit every matching event to the sink."""
    queue = bus.subscribe()
    while True:
        event = await queue.get()
        if sink.event_filter.matches(event):
            sink.emit(event)
