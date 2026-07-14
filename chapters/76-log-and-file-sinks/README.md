# Chapter 76 - Log and file sinks

> **Goal:** generalise "push events out" from just webhooks to any **sink**, and add
> two more that need no network and no dependencies: a console log and a JSONL file.

## Sinks, plural

Chapter 69 POSTed events to webhooks. But the event bus (chapter 16) was always
meant for many consumers - the live dashboard is already one. So a sink is now just
"a filter plus an `emit`", captured by a small `Sink` protocol:

```python
class Sink(Protocol):
    @property
    def event_filter(self) -> EventFilter: ...
    def emit(self, event: Event) -> None: ...
```

Three ship in the box, all standard-library only:

- **`WebhookSink`** - POST the event to a URL (chapter 69);
- **`LogSink`** - `print` the event as one line of JSON (adder's log output; watch the
  chain in a terminal, no browser);
- **`FileSink`** - append the event as a line of JSON to a file (JSONL) - an audit
  trail you can replay or `grep` later.

`run_sink(bus, sink)` is one loop: subscribe, keep what matches the filter, call
`emit`. It works for every sink type, so adding another (a queue, a socket) is just
a new `emit`.

## One config shape

A single `sinks` list, each entry `{type, target, ...filters}`:

```json
{
  "sinks": [
    { "type": "log",     "types": ["rollback"] },
    { "type": "file",    "target": "events.jsonl", "policies": ["<policyid>"] },
    { "type": "webhook", "target": "https://example.com/hook", "addresses": ["addr_test1..."] }
  ]
}
```

`type` picks the sink (default `webhook`); `target` is the URL or file path (a log
sink needs none); the filter fields (`types` / `addresses` / `policies` / `assets`)
are the same everywhere. The older `webhooks` list still works as shorthand for
webhook sinks, so nothing breaks.

The filter-building moved to `patterns.event_filter_from_dict` so every sink type
shares it.

## Pure where it can be

`LogSink.emit` and `FileSink.emit` are plain and **unit-tested** (a captured stdout,
a temp file) - unlike the webhook POST, which needs the network. Only `run_sink`'s
forever-loop is `# pragma: no cover`. Dispatch (`build_sink` / `build_sinks`) and the
config parsing are tested too.

## Test first (red), make it pass (green)

`test_sinks.py` covers the log and file `emit`, the `type` dispatch (including the
`url` shorthand and an unknown type), and `build_sinks`. `test_config.py` covers the
`sinks` list. `make check` stays green at 100 percent.

## What we built

- A `Sink` protocol; `LogSink` and `FileSink`; `build_sink` / `build_sinks`; a
  general `run_sink` loop (`sinks.py`).
- `patterns.event_filter_from_dict` (shared filter-building).
- `Config.sinks`; the live runner wires `webhooks` (shorthand) and `sinks` together.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch76): log and file event sinks under a general sinks config"
git tag ch76
```
