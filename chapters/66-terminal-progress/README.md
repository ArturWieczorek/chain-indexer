# Chapter 66 - Terminal progress (so the console is not silent)

> **Goal:** show sync progress in the terminal, so you can see the indexer working
> without opening the browser.

## The problem

`python -m chainidx.live` printed one line - `live view on ...` - and then went
quiet (only uvicorn warnings). All the "is it actually syncing?" feedback lived in
the web view. For a first run that is unnerving: nothing on screen looks like
nothing happening.

## The fix

A periodic one-line summary, printed every ten seconds:

```
following the chain: tip block #12873, 12873 applied, 2 rolled back
```

The phrasing is a pure function, `follow.format_progress(height, applied,
rolled_back)`, so it is unit-tested; the periodic printing is a small
`_progress_loop` added to the live runner's `asyncio.gather`, alongside the server,
the follower, and the snapshot loop (all coverage-omitted, since they need a live
loop and a node). The existing `make run` demo loop now uses the same formatter, so
there is one phrasing in one place.

The counts come straight from `FollowStats` (chapter's-old bookkeeping): `applied`
climbs as blocks arrive, and `rolled back` ticks up on a reorg - so a rollback is
visible in the terminal too, not only in `/live`.

## Test first (red), make it pass (green)

`test_follow.py` pins the summary's shape (the tip height, the applied count, the
rolled-back count all appear). `make check` stays green at 100 percent.

## What we built

- `follow.format_progress`, a pure one-line summary (tested).
- `_progress_loop` in the live runner, printing it every ten seconds.
- The README's Getting-started note now sets the right expectation for the terminal.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch66): periodic terminal progress so the console is not silent"
git tag ch66
```
