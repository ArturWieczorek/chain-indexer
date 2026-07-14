# Chapter 24 - Live stake and saturation

> **Goal:** finish the pool pages to cardanoscan level by adding **live stake** and
> **saturation** - ledger-state numbers from chapter 20's local-state-query,
> persisted so the read-only API can serve them.

Chapter 22's pool pages showed blocks minted, delegators, pledge, and margin - all
derivable from the indexed chain. The two numbers still missing are the ones an
operator and a delegator care about most: how much stake the pool controls right
now (**live stake**) and how close it is to the ideal size (**saturation**). Those
are ledger state, so they come from local-state-query, not from blocks.

## The persistence problem

The API is a synchronous, read-only view over SQLite; local-state-query is an
asynchronous conversation with the node. Querying the node inside every web
request would be slow and awkward. So we do what cardano-db-sync does: take a
**snapshot** of the ledger numbers periodically and store them, then serve the
stored values.

- Migration 6 adds two small tables: `pool_stat` (live stake per pool) and
  `ledger_stat` (scalars like `n_opt`). They are *not* block-keyed and do not roll
  back - they are a refreshed snapshot, replaced wholesale each time.
- `store.record_stake_distribution(stakes, n_opt)` replaces the snapshot in one
  transaction.
- `pool_detail` / `pool_summaries` now fill in `live_stake` and `saturation`.

## Saturation

Saturation compares a pool's stake to the ideal share, which is `1 / n_opt` where
`n_opt` is the protocol's target number of pools (500 on our cluster). So:

```
  saturation = live_stake_fraction * n_opt
```

A saturation of 1.0 (100%) means the pool holds exactly the ideal share; above
1.0 it is oversaturated and earns diminishing rewards. `n_opt` comes from the
protocol parameters (we added it to the params parser), recorded alongside the
stakes.

## Refreshing the snapshot

The live runner (`make live`) gains a background task that every 20 seconds runs
a local-state-query snapshot and calls `record_stake_distribution`. Follower,
web server, and snapshot loop all run in one asyncio process, so they share the
one SQLite handle without extra machinery. A transient node hiccup just skips a
refresh; the previous snapshot stays until the next success.

The pool pages now show a Live stake and a Saturation column (and the detail page
the exact percentages). On our cluster the three pools split the stake roughly
evenly, each far below saturation - exactly what a tiny testnet looks like.

## Test first (red), make it pass (green)

Tests cover the params parser exposing `n_opt`, the store recording a snapshot and
computing `live_stake` and `saturation` (0.2% stake at `n_opt` 500 gives
saturation 1.0), and the API pool payload carrying the new fields. The periodic
snapshot loop is part of the live runner and is excluded from coverage like the
other live-only code. `make check` stays green and fully covered.

## What we built

- Migration 6 (`pool_stat`, `ledger_stat`) and `store.record_stake_distribution`.
- `live_stake` and `saturation` on `PoolSummary`, the API, and the pool pages.
- A periodic snapshot task in the live runner; `n_opt` in the params parser.

## Glossary

- **Live stake**: the stake a pool currently controls, as a fraction of the
  total; ledger state, from local-state-query.
- **Saturation**: live stake relative to the ideal `1 / n_opt` share; 100% is the
  sweet spot.
- **Snapshot**: a periodically refreshed copy of ledger numbers, stored so the API
  can serve them without querying the node per request.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch24): live stake and saturation on pool pages"
git tag ch24
```

## Next up

[Chapter 25 - Accounts and rewards](../25-accounts/): stake-account pages using
local-state-query's account and reward queries, which take a set of credentials as
an argument - the first query we send with a payload.
