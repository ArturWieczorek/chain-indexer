# Chapter 57 - Header status and theme label

> **Goal:** two small header fixes. The tip height sat awkwardly next to the
> colour swatches; it belongs with the tip time. And the theme button said
> "theme" rather than which theme is active.

## Tip moves to the banner

The header status now shows a compact **connection indicator** (`online` /
`offline`, coloured), not the tip height. The tip height moves into the network
banner next to the tip time, where it reads naturally alongside the current epoch
and progress. `/network` gains a `tip_height` field for that (from the stored
tip), so the banner shows tip and tip time together.

## Theme button shows the mode

`applyTheme` now sets the button label to the active theme (`☾ dark` / `☀ light`),
on both the explorer and the live page, so it is clear what is selected rather than
a static "theme".

## Test first (red), make it pass (green)

The network test now also asserts `/network` returns the `tip_height`. The header
and label changes are client-side. `make check` stays green and fully covered.

## What we built

- `/network` returns `tip_height`; the banner shows tip + tip time together.
- The header status is a connection indicator; the theme button shows the current
  mode on both pages.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch57): move tip to the banner, connection status, themed toggle label"
git tag ch57
```
