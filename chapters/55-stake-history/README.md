# Chapter 55 - Per-epoch stake history (opt-in)

> **Goal:** chart a pool's live stake over epochs - the honest, feasible slice of a
> rewards/trend view. It accumulates from local-state-query snapshots, so it only
> fills going forward, and it is off by default.

## Why this is the honest version

The node computes stake and rewards; no wire protocol carries them in blocks, and
we do not recompute them (that would mean reimplementing the ledger). We already
read the current stake distribution via local-state-query each snapshot - but we
overwrite it, keeping only the latest. To get a trend, we also record it **keyed by
epoch**, so history accumulates one point per epoch.

Two honest limits carry over: it only has data from when recording starts (nothing
retroactive), and it tracks **stake**, not rewards (LSQ gives current reward
balances, not per-epoch reward amounts). So this chapter charts stake per epoch and
stops there.

## Opt-in

Recording adds a periodic write and a growing table, so it is **off unless**
`CHAINIDX_STAKE_HISTORY` is set. Migration 18 adds a `stake_history` table (one row
per epoch and pool, ledger state so not block-keyed and not rolled back).
`store.record_stake_history` upserts a snapshot for an epoch (re-recording the same
epoch overwrites), and `store.pool_stake_history` reads a pool's series. The
snapshot loop records it only when the flag is set. `/pools/{id}` returns
`stake_history`, and the pool page draws a live-stake-per-epoch chart when there is
data.

## Test first (red), make it pass (green)

A test records two epochs (with a within-epoch overwrite) and checks the pool
detail returns the series in epoch order with the latest value per epoch. `make
check` stays green and fully covered.

## What we built

- Migration 18 `stake_history`; `store.record_stake_history` /
  `store.pool_stake_history`; the snapshot loop records per-epoch stake when
  `CHAINIDX_STAKE_HISTORY` is set.
- `/pools/{id}` `stake_history` and a live-stake-per-epoch chart on the pool page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch55): opt-in per-epoch stake history and chart"
git tag ch55
```

## Where this leaves the project

Every requested feature is in: the full node-to-client protocol suite, a
cardanoscan-shaped explorer (blocks, transactions, mempool, epochs, pools with full
on-chain details, governance, certificates, withdrawals, tokens with CIP-25/68
metadata and images, top holders, analytics), off-chain metadata, theming, and now
an honest stake trend. The one thing deliberately not faked is historical
reward/ROS data, which needs the ledger's own reward computation.
