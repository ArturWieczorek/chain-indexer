# Chapter 80 - Which chain am I indexing?

> **Goal:** let a client confirm the indexer is pointed at the network it expects,
> so preprod data never gets mistaken for preview (or mainnet).

## Why

With more than one network running side by side (chapter 65), and no field tying a
database to a network, it is easy to query the wrong port. The genesis file already
says which network it is (`networkMagic`); we just were not surfacing it.

## What it does

`NetworkParams` now reads `networkMagic` from the Shelley genesis, and two endpoints
report it:

- `GET /health` gains `network_magic` (42 local, 1 preprod, 2 preview, 764824073
  mainnet), so a one-line health check also confirms the chain.
- `GET /network` includes `network_magic` alongside the timing parameters.

Both are `null` / absent when no genesis is configured (the indexer runs without
one; it just cannot do slot-to-time math).

## Test first (red), make it pass (green)

`test_network.py` checks `from_genesis` reads the magic; `test_api.py` checks it
appears in `/health` and `/network`. `make check` stays green at 100 percent.

## What we built

- `NetworkParams.network_magic` (from genesis); `network_magic` in `/health` and
  `/network`.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch80): report network_magic in /health and /network"
git tag ch80
```
