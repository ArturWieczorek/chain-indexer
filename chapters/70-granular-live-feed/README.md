# Chapter 70 - A granular live feed

> **Goal:** make the `/live` page show per-transaction detail, now that the event
> bus carries it (chapter 68).

## The idea

The live feed showed a line per block and per certificate, but nothing per
transaction - so a busy block was just "12 txs" with no detail. Chapter 68 added a
`transaction` event carrying the outputs, the ADA moved, the assets, and the mint
count. This chapter is the payoff: the feed renders those, and the reorg entry (the
project's headline) stands out in red.

## What changed

Frontend only (`web/live.html`), consuming events that already exist:

- A **`transaction`** line per transaction: the short tx hash, its output count, the
  ADA moved, `minted N` when it mints, and the first policy it touches.
- The existing **`rollback`** entry keeps its red highlight, so a chain rollback is
  the one thing you cannot miss in the stream.

No API or store change: the WebSocket already forwards every event the follower
publishes, and this is just a new branch in the page's event handler.

## Test first (red), make it pass (green)

The `/live` route is covered as before (it serves the page); the page's rendering is
static JavaScript with no unit surface, like the rest of the explorer front end.
`make check` stays green at 100 percent.

## What we built

- A `transaction` branch in the `/live` feed handler, showing per-tx detail.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch70): a granular live feed with per-transaction detail"
git tag ch70
```
