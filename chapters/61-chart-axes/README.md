# Chapter 61 - Chart axes and gridlines

> **Goal:** the charts drew a line but no scale - no numbers, nothing to read a
> value against. Add gridlines with y-value labels and x-axis epoch labels so the
> charts are actually legible.

Every line chart (analytics transactions/blocks/fees, and the pool's blocks,
stake, made-vs-expected, and saturation) shared two bare helpers, `lineChart` and
`multiLine`. They now render a small set of axes:

- **Horizontal gridlines** at 0, 25, 50, 75, 100% of the maximum, each labelled
  with the formatted value (the same `fmt` the tooltip uses - so ada, percentages,
  or counts render correctly).
- **X-axis epoch labels** at the first, middle, and last points (`e<epoch>`).

The geometry is shared through a `CHART` constant and `chartX`/`chartY`/`chartAxes`
helpers, with left/bottom padding for the labels, so both chart kinds line up. The
data points still carry their hover tooltip. Purely presentational; no backend or
endpoint changes.

## Test

No Python changed; `make check` stays green. Legibility is verified by opening the
analytics and pool pages.

## What we built

- `chartAxes` (gridlines + y-value labels + x epoch labels) and shared chart
  geometry, used by both `lineChart` and `multiLine`.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch61): axes, gridlines, and value labels on the charts"
git tag ch61
```
