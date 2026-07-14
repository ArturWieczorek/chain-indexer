# Chapter 69 - The webhook sink

> **Goal:** push filtered events out to HTTP endpoints - adder's "output" idea -
> completing the kupo + adder pairing.

## The idea

Chapter 68 gave us rich events and a filter. A **`WebhookSink`** ties them to an
output: it subscribes to the event bus, keeps only the events matching its
`EventFilter`, and POSTs each survivor as JSON to a configured URL. Because a
rollback is just another event on the bus, a webhook can react to a **reorg** - the
thing a naive block notifier misses.

## Configuration

A `webhooks` list in the JSON config, one entry per sink - a URL plus the filter
fields (all optional; omit to match everything):

```json
{
  "webhooks": [
    { "url": "https://example.com/hook", "addresses": ["addr_test1..."] },
    { "url": "https://example.com/reorgs", "types": ["rollback"] },
    { "url": "https://example.com/mynft", "policies": ["<policyid>"] }
  ]
}
```

`sink_from_dict` turns one entry into a `WebhookSink`: addresses are decoded from
bech32 to the hex the events carry, policies and assets are lower-cased, and the
whole thing becomes an `EventFilter`. The live runner builds one sink per entry and
runs them alongside the follower.

## Pure where it can be, integration where it must be

Building sinks from config and encoding the JSON payload are pure and unit-tested.
The two things that need the outside world - the actual HTTP `POST` and the
subscribe-forever loop - are marked `# pragma: no cover`, like `offchain` and the
mini-protocol clients. The POST is best-effort (`contextlib.suppress`): a webhook
that is down must never stall indexing.

## Test first (red), make it pass (green)

`test_webhook.py` covers `sink_from_dict` (filter built, addresses normalised),
`sinks_from_config`, and the JSON payload. `test_config.py` covers parsing the
`webhooks` list (and dropping malformed entries). `make check` stays green at 100
percent.

## What we built

- `webhook.py`: `WebhookSink`, `sink_from_dict` / `sinks_from_config`,
  `encode_payload` (pure), and the `run_sink` loop + `_post` (integration).
- `Config.webhooks`; the live runner wires one sink per entry.
- A "Webhooks" section in the project README.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch69): a webhook sink that pushes filtered events, reorgs included"
git tag ch69
```

## Where this leaves the kupo + adder work

Both halves are in: kupo-style **querying** (a `/matches` pattern API and datums by
hash) and adder-style **pushing** (rich, filtered events to webhooks, rollbacks
included), all reusing the index and the bus we already had. The remaining piece is
reference scripts (`/scripts/{hash}`), held back until its hash can be verified
against a real captured script.
