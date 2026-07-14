# Chapter 21 - Epochs and the dashboard

> **Goal:** turn slots into epochs and wall-clock times, aggregate per-epoch stats
> from the blocks we already index, and add the first real explorer sections: a
> current-epoch banner, an Epochs page, and block timestamps - a step toward the
> cardanoscan surface.

The chain thinks in **slots**, not dates, and groups slots into **epochs**. Real
explorers show "epoch 77, 12% complete" and "block produced at 20:41:07". This
chapter adds that, using one new fact from chapter 20's local-state-query (the
system start) plus two numbers from genesis.

## The three numbers, and the math

From the Shelley genesis we read:

- `system_start` - the wall-clock time of slot 0;
- `slot_length` - seconds per slot (0.2 on our cluster);
- `epoch_length` - slots per epoch (1000 on our cluster).

From those, everything follows, and it is pure arithmetic:

```
  epoch_of(slot)   = slot // epoch_length
  slot_time(slot)  = system_start + slot * slot_length
  progress(tip)    = (tip // epoch_length, tip % epoch_length, that / epoch_length)
```

`network.py` holds `NetworkParams` and these functions. Being pure, they are
tested exactly: slot 0 is the system start, slot 5 (at 0.2s) is one second later,
epoch 1 begins at slot 1000, and slot 75125 is epoch 75, 12.5% in.

> **Simplification, stated.** This assumes one uniform slot length for the whole
> chain, which holds for a Shelley-and-later network like ours. A chain spanning
> the Byron era (different slot length) would need per-era math - noted, not done.

## Epoch aggregates without a new column

Cardanoscan's Epochs page lists, per epoch, the block and transaction counts. We
already store every block with its slot and `tx_count`, so we can aggregate by
grouping on `slot_no / epoch_length` - integer division gives the epoch number
directly, no new column needed:

```sql
SELECT slot_no / :epoch_length AS epoch_no,
       COUNT(*) AS blocks, SUM(tx_count) AS txs,
       MIN(slot_no) AS start_slot, MAX(slot_no) AS end_slot
FROM block GROUP BY slot_no / :epoch_length
```

`store.epoch_summaries` and `store.epoch_summary` return that as `EpochSummary`
records. Start and end times come from `NetworkParams` in the API layer.

## Wiring network params in

The API factory now takes an optional `NetworkParams`. When present:

- `/epochs` and `/epochs/{no}` return the aggregates with start/end times;
- `/network` reports the system start, slot/epoch length, and - from the tip - the
  current epoch, how far through it we are, and the tip's wall-clock time;
- every block gains an `epoch_no` and a `time`.

Where do the params come from at runtime? A Shelley genesis file, pointed to by
`CHAINIDX_GENESIS`. `make explorer` and `make live` load it if set; without it,
epoch features are simply absent (the API returns empty/`available: false`), so
nothing breaks when it is not configured.

## The explorer grows a nav

The explorer page gains a small navigation bar (Blocks, Epochs), a **current-epoch
banner** with a progress bar on the home page, an **Epochs** list (each epoch links
to its detail page), and **timestamps and epoch numbers on block pages**. This is
the first of several cardanoscan-style sections; Pools and Governance follow in the
next chapters.

## Test first (red), make it pass (green)

Tests cover the network math (from a genesis fixture and inline), the store's
epoch grouping, and the API's `/epochs`, `/epochs/{no}`, and `/network` (both with
params and the empty-without-params case), plus block timestamps. `make check`
stays green and fully covered.

## What we built

- `chainidx.network`: `NetworkParams` (+ `from_genesis`) and the slot/epoch/time
  math, with `EpochProgress`.
- `EpochSummary` and `store.epoch_summaries` / `epoch_summary`.
- API: `/epochs`, `/epochs/{no}`, `/network`, and block timestamps; the app
  factories load params from `CHAINIDX_GENESIS`.
- Explorer: a nav bar, a current-epoch banner, an Epochs page, and block times.

## Glossary

- **Slot**: the chain's unit of time; a block may or may not be made each slot.
- **Epoch**: a fixed number of slots (1000 here); stake and rewards are reckoned
  per epoch.
- **System start**: the wall-clock time of slot 0, from genesis / local-state-query.
- **Epoch progress**: how far through the current epoch the tip is.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch21): epochs, network params, and a dashboard banner"
git tag ch21
```

## Next up

[Chapter 22 - Pools](../22-pools/): a proper Pools section - index which pool
minted each block, and combine registration parameters with chapter 20's live
stake distribution to show pool pages with live stake, saturation, and blocks
produced.
