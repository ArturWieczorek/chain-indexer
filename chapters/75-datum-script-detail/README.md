# Chapter 75 - Datums and scripts in the explorer

> **Goal:** surface the datum hash and reference-script hash that already ride on
> every output, as clickable links to detail pages - instead of a dead-end nav
> section.

## The choice: contextual links, not an empty nav tab

`/datums/{hash}` and `/scripts/{hash}` (chapters 67 and 73) are kupo-style **lookups
by hash**, not browse lists - and reference scripts are rare, so a top-level
"Scripts" nav section would sit empty on most chains and would need a "list all
scripts" query we do not have. So this chapter surfaces them where they actually
occur: on an output.

## What changed (front-end only)

- Outputs now show a **Datum / Script** column - on the transaction UTXOs tab and on
  the address page. A datum hash and a reference-script hash each render as a link.
- Two small detail pages: `#/datum/{hash}` (shows the datum CBOR from
  `/datums/{hash}`) and `#/script/{hash}` (shows the language and CBOR from
  `/scripts/{hash}`), each with a friendly message when the hash was never seen.
- The Back link from chapter 74 gets its final styling (a rounded button with an
  arrow) so it reads as a control, not plain text.

No API or store change: the hashes were already in the `/txs` and `/addresses`
responses; the explorer just renders and links them now.

## Test first (red), make it pass (green)

The endpoints these pages call are covered by chapters 67 and 73; the rendering is
static front-end JavaScript, like the rest of the explorer. `make check` stays green
at 100 percent.

## What we built

- An `extrasCell` that links an output's datum and reference-script hashes.
- `#/datum/{hash}` and `#/script/{hash}` detail pages (with a `cborPanel` helper).
- Final styling for the Back link.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch75): clickable datum and reference-script hashes with detail pages"
git tag ch75
```
