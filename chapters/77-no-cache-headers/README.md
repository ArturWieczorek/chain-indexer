# Chapter 77 - Do not cache the explorer pages

> **Goal:** make a restarted server's updated explorer show up without a hard
> refresh.

## The papercut

The explorer is a single HTML page the browser loads once and then navigates inside
via the URL fragment. Browsers cache that HTML, so after the server restarts with a
changed page, a plain reload can still show the old one - you had to remember
Ctrl-Shift-R.

## The fix

Serve the two HTML routes (`/` and `/live`) with `Cache-Control: no-cache`. That does
not stop caching outright; it tells the browser to **revalidate** with the server
before reusing the page, so a changed page is fetched fresh while an unchanged one
still returns quickly (`304`). One header on each route.

## Test first (red), make it pass (green)

The existing explorer and live-page tests now also assert the `cache-control` header
is `no-cache`. `make check` stays green at 100 percent.

## What we built

- `Cache-Control: no-cache` on the `/` (explorer) and `/live` (dashboard) responses.

## Commit and tag

```bash
git add -A
git commit -m "fix(ch77): no-cache the explorer pages so restarts show up"
git tag ch77
```
