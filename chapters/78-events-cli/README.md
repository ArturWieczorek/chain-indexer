# Chapter 78 - `chainidx events`: tail the chain in a terminal

> **Goal:** a command-line tail of the event stream - the same events the webhooks
> get, printed as JSON lines - so a test or a shell can react without a browser, a
> database, or an HTTP server.

## Why

The event bus already feeds the live dashboard and the sinks. But in a test or a CI
job you often just want to *watch the stream in a terminal* and act on it - await a
transaction, assert a rollback happened - without standing up the web server or a
database. That is exactly what a `LogSink` does; this chapter exposes it as a CLI
command.

## What it does

```bash
chainidx events --socket "$CARDANO_NODE_SOCKET_PATH" --magic 42
```

It follows the node (into an in-memory store - we only want the stream) and prints
every event as one line of JSON. The same filter flags as the sinks narrow it, and
they repeat:

```bash
# only rollbacks - a clean signal for a reorg test
chainidx events --socket "$SOCK" --magic 42 --type rollback

# only transactions touching a policy, piped to jq
chainidx events --socket "$SOCK" --magic 42 --policy "$POLICYID" | jq .
```

A real line (a transaction that minted an NFT, captured from a local cluster):

```json
{"type": "transaction", "tx_hash": "38f30f8d...7201", "block_no": 19674,
 "addresses": ["60612f89...b28a"], "policies": ["dee42126...54b8"],
 "assets": ["dee42126...54b8.436861696e4964784e4654"],
 "lovelace": 14991019984717062, "output_count": 2, "mint_count": 1}
```

Filters combine like everywhere else: any of a field's values, all of the given
fields. Pipe it to `jq`, `grep`, or a file.

## Reusing what we have

The command is a thin wrapper: a `Follower` with an in-memory `SqliteStore`, an
`EventBus`, and a `LogSink` built from `event_filter_from_dict` (the same builder the
config sinks use) driven by `run_sink`. It drives a live node, so like the other live
CLI commands (`state`, `submit`, `follow`) it is marked `# pragma: no cover`; the
pieces it composes are all unit-tested already.

## What we built

- A `chainidx events` command that tails filtered events as JSON lines.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch78): a chainidx events command to tail filtered events as JSON lines"
git tag ch78
```
