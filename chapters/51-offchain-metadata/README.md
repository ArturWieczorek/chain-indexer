# Chapter 51 - Off-chain pool metadata

> **Goal:** show a pool's name and ticker. These are not on-chain: the
> registration only anchors a URL (chapter 50); the human-facing JSON lives there,
> off-chain. This chapter fetches it - but only when explicitly enabled.

## Opt-in by design

Reaching out to the network is a side effect the indexer should not do by default,
and unit tests must never touch the network. So fetching is **opt-in**: it happens
only when the server is started with `CHAINIDX_FETCH_METADATA` set. The parsing is
pure and tested; the HTTP fetch is a separate, coverage-excluded function.

- `offchain.parse_pool_metadata(raw)` reads the known fields (name, ticker,
  homepage, description) out of the JSON, returning `None` for anything unusable.
- `offchain.fetch_pool_metadata(url)` does the actual `urllib` GET (capped read,
  short timeout, `None` on any error) and parses the result.

## Wiring it in

`create_app` gains an optional `metadata_fetcher` callable (the same dependency-
injection pattern as the mempool source): the pool endpoint calls it with the
pool's metadata URL and, if it returns something, puts it on the response as
`metadata`. Unit tests pass a fake fetcher to cover both the hit and the miss;
the live runner passes the real `fetch_pool_metadata` only when
`CHAINIDX_FETCH_METADATA` is set. The pool page shows the name and ticker in its
heading and a small off-chain metadata panel.

Because the fetcher is injected, the default build never fetches, and the whole
network path stays out of the coverage gate.

## Test first (red), make it pass (green)

`parse_pool_metadata` is tested for the field subset and for rejecting non-JSON,
non-object, and field-less input. An API test registers a pool with a metadata URL
and checks that a fake fetcher's name/ticker appear, that a fetcher returning
`None` adds nothing, and that with no fetcher there is no metadata. `make check`
stays green and fully covered.

## What we built

- `offchain.parse_pool_metadata` (pure) and `fetch_pool_metadata` (opt-in HTTP).
- `create_app` `metadata_fetcher` injection, threaded through the explorer and live
  apps; the live runner enables it on `CHAINIDX_FETCH_METADATA`.
- Pool name/ticker on the pool page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch51): fetch off-chain pool metadata (name/ticker) when enabled"
git tag ch51
```

## Next up

Rendering asset images from metadata, via a configurable gateway.
