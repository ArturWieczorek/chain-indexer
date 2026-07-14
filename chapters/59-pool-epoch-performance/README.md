# Chapter 59 - Pool performance: expected vs made, and saturation

> **Goal:** the pool graphs that per-epoch stake history (chapter 55) newly makes
> possible - expected-vs-made blocks and saturation over epochs - which earlier
> chapters correctly said were out of reach.

## What changed since "not possible"

Earlier the per-epoch trend was infeasible because we had no historical active
stake. Chapter 55 started capturing it (going forward, via local-state-query). With
that, two of the previously-impossible series become computable:

- **Expected blocks** per epoch: `NetworkParams.expected_blocks(stake_fraction)` =
  `activeSlotsCoeff * epoch_length * stake_fraction`. The coefficient now comes
  from the Shelley genesis; the stake fraction comes from the epoch's captured
  history.
- **Saturation** per epoch: `stake_fraction * n_opt` (n_opt from the protocol
  parameters).

Rewards and ROS remain out - those need the ledger's reward calculation, which no
protocol carries and which we do not recompute.

`/pools/{id}` gains an `epoch_performance` array (per captured epoch: stake,
saturation, expected blocks, and blocks actually made). The pool page draws a
**made vs expected** two-line chart and a **saturation per epoch** chart with the
`multiLine`/`lineChart` helpers.

## Honesty about the data

These charts only cover epochs for which stake history was captured (forward-only,
and gappy if the indexer was down) - never backfilled, because LSQ cannot serve
past snapshots. "Made" comes from indexed blocks, so the comparison is
apples-to-apples only for fully-indexed epochs; the current in-progress epoch
naturally shows fewer made than expected until it closes. Nothing is fabricated: a
missing epoch is simply absent.

## Test first (red), make it pass (green)

`NetworkParams` tests cover reading `activeSlotsCoeff` from genesis and
`expected_blocks`. An API test records an epoch's stake and a block minted in it,
then checks `epoch_performance` reports the made count, the expected count
(`f * epoch_length * stake`), and the saturation (`stake * n_opt`). `make check`
stays green and fully covered.

## What we built

- `NetworkParams.active_slot_coeff` (from genesis) and `expected_blocks`.
- `/pools/{id}` `epoch_performance`; a `multiLine` chart helper; made-vs-expected
  and saturation charts on the pool page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch59): pool expected-vs-made blocks and saturation per epoch"
git tag ch59
```

## Next up

Small status-colour polish on the live page.
