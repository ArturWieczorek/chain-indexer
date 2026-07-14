# Chapter 60 - Live status colour

> **Goal:** a one-line polish - the live view's connection status now shows green
> when connected and red when the socket drops, matching the explorer's coloured
> status.

The live page's status read "live" / "reconnecting..." in plain grey. It now shows
a coloured dot: **green "live"** while the WebSocket is open, **red "offline"** when
it closes (before it retries). Purely presentational, on the live page only.

## Test

No Python changed; `make check` stays green.

## What we built

- A coloured connection indicator on the live view (green connected, red offline).

## Commit and tag

```bash
git add -A
git commit -m "feat(ch60): colour the live view connection status"
git tag ch60
```
