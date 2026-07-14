# Chapter 62 - A readable blocks-per-epoch chart

> **Goal:** the pool's "Blocks produced per epoch" chart plotted every epoch the
> pool ever minted in - hundreds of points squeezed into the panel width, so it
> read as a tiny scribble. Show a recent window instead.

The other pool charts (stake, saturation, made-vs-expected) come from the captured
stake history - a handful of points - so they were already legible. Only the
blocks chart used the full per-epoch history from the block table. It now:

- keeps the **lifetime stats** (lifetime blocks, epochs minting, average) over the
  whole history, but
- charts only the **last 40 epochs**, labelled as such, so each point has room and
  the axes (chapter 61) are readable.

This mirrors what the analytics page already does with its per-epoch charts.
Presentational only.

## Test

No Python changed; `make check` stays green.

## What we built

- The pool blocks-per-epoch chart is limited to a recent window (last 40), while
  the lifetime performance stats still cover all epochs.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch62): show a recent window in the pool blocks-per-epoch chart"
git tag ch62
```
