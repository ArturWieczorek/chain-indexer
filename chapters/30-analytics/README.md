# Chapter 30 - Analytics

> **Goal:** an analytics page - network totals and a blocks-per-epoch chart -
> rendered as inline SVG in the explorer, with no chart library.

Explorers have an analytics view: totals at a glance and a trend chart. We have all
the numbers already; this chapter adds a small summary endpoint and draws a chart
from the per-epoch data we built in chapter 21.

## A tiny summary endpoint

`/analytics/summary` returns the network totals - blocks, transactions, active
pools, DReps, governance actions - each a one-line store query
(`store.total_transactions` is the only new one: `SUM(tx_count)` over blocks). It
is pure aggregation, so it is easy to test exactly.

## A chart without a library

The analytics page fetches `/epochs` and draws **blocks per epoch** as an inline
SVG bar chart - one `<rect>` per epoch, heights scaled to the tallest bar, each
with a `<title>` tooltip. No chart library, no build step; the bars use the same
accent colour as the rest of the explorer and turn green on hover, so it fits the
existing design. The chart scrolls horizontally if there are many epochs.

Keeping it as raw SVG is deliberate: it is a few lines, it has no dependencies, and
it shows that "a chart" is just rectangles positioned by data.

## Test first (red), make it pass (green)

Tests cover `store.total_transactions` (summing across blocks) and
`/analytics/summary` (the totals for a small fixture). The SVG is drawn
client-side; the tests pin the data behind it. `make check` stays green and fully
covered.

## What we built

- `store.total_transactions` and the `/analytics/summary` endpoint.
- An Analytics page: network total tiles and a blocks-per-epoch SVG chart.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch30): analytics page with a blocks-per-epoch chart"
git tag ch30
```

## Next up

[Chapter 31 - Tokens](../31-tokens/): a tokens/assets section - list the native
assets in circulation and a per-asset page - completing the last of the
cardanoscan top-level sections.
