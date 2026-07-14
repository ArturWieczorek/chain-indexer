# Chapter 48 - Richer pool detail

> **Goal:** bring the pool page closer to a professional explorer's: the pool's
> fixed cost and metadata anchor, and a blocks-per-epoch chart of its minting.

## More from the registration certificate

A pool registration certificate carries more than the pledge, margin, and reward
address we already decode: it also has a **cost** (the pool's fixed fee per epoch)
and a **metadata anchor** (a URL and hash pointing at off-chain JSON that holds the
pool's name and ticker). The decoder now reads the cost (`cert[4]`) and the
metadata URL (`cert[9][0]`, or empty when the anchor is null). Migration 15 adds
`cost` and `metadata_url` columns to `pool_registration`, the `CertIndexer` fills
them, and they flow through `PoolSummary` to the API and pool page.

Fetching that off-chain JSON to show the name and ticker is a later step (a network
fetch, gated by configuration); here we surface the URL itself.

## A blocks-per-epoch chart

`store.pool_blocks_by_epoch` counts the pool's minted blocks per epoch (grouping
the `block` table by `slot_no / epoch_length`, filtered to the pool's issuer id).
`/pools/{id}` returns the series, and the pool page draws it with the same
`lineChart` helper the analytics page uses.

## Test first (red), make it pass (green)

A decoder test reads the cost and metadata URL from a pool registration cert (and
the null-anchor case). An API test registers a pool with a cost and metadata URL,
mints a block in two different epochs, and checks the pool detail reports the cost,
the URL, and one block per epoch. `make check` stays green and fully covered.

## What we built

- `PoolRegistration`/`PoolSummary` gain `cost` and `metadata_url`; the decoder
  reads them; migration 15 stores them.
- `store.pool_blocks_by_epoch`; `/pools/{id}` returns cost, metadata URL, and a
  blocks-per-epoch series; the pool page shows them with a chart.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch48): richer pool detail with cost, metadata anchor, and a blocks chart"
git tag ch48
```

## Next up

Mint transactions (a Tokens sub-view listing minting transactions), then fetching
off-chain metadata (pool name/ticker, asset images) behind configuration.
