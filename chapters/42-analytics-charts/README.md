# Chapter 42 - Analytics time series

> **Goal:** turn the analytics view into a set of time-series charts - transactions,
> blocks, and fees per epoch - the way a professional explorer plots activity over
> time.

The analytics page had a single blocks-per-epoch bar chart. This chapter replaces
it with proper time series and adds fees, a metric we could only show once
transactions carried their fee (chapter 35).

## A per-epoch aggregate with fees

`store.epoch_stats` groups blocks by epoch (`slot_no / epoch_length`) and
left-joins their transactions, so it can report, per epoch:

- the block count (a `DISTINCT` count, so the join does not inflate it),
- the transaction count, and
- the total fees paid.

It returns `EpochStats` rows, newest epoch first.

## API and explorer

- `/analytics/timeseries` returns the per-epoch series (with each epoch's start
  time when network parameters are configured; empty without them).
- A small reusable inline-SVG `lineChart` helper draws an area-and-line chart. The
  Analytics page now shows **Transactions per epoch**, **Blocks per epoch**, and
  **Fees per epoch**, alongside the existing totals and the top-holder tables.

## Test first (red), make it pass (green)

A store test spreads transactions with fees across two epochs and checks the
per-epoch block, transaction, and fee totals (newest first). An API test checks the
empty series without network parameters and the populated series (with fees and
time) with them. `make check` stays green and fully covered.

## What we built

- `EpochStats` model; `store.epoch_stats`.
- `/analytics/timeseries`; a `lineChart` helper and three time-series charts on the
  Analytics page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch42): analytics time-series charts for transactions, blocks, and fees"
git tag ch42
```

## Next up

A mempool view - the pending transactions a node holds before they reach a block -
which needs the fifth node-to-client mini-protocol, local-tx-monitor (id 9),
probed against a live node first.
