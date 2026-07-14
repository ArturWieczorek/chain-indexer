# Chapter 54 - Richer recent blocks on the pool page

> **Goal:** a small improvement - the pool page's "Recent blocks" listed only
> hashes; show each block's height, epoch, and slot too.

`store.recent_blocks_by_pool` returns the hashes of a pool's recent blocks (it
stays as-is, since other code and tests rely on that shape). The pool endpoint now
loads each of those blocks and returns them as full block records - the same
`_block` shape the block list uses - so `recent_blocks` carries `block_no`,
`slot_no`, `epoch_no` (with network parameters), and the hash. The pool page shows
them as a table with Height, Epoch, Slot, and Hash columns, each linking to its
page.

## Test first (red), make it pass (green)

The pool detail test (which mints blocks in two epochs) now also checks that
`recent_blocks` entries are ordered newest-first and carry the block height, slot,
and epoch. `make check` stays green and fully covered.

## What we built

- The `/pools/{id}` `recent_blocks` payload is now full block records; the pool
  page shows height, epoch, and slot alongside the hash.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch54): show height, epoch, and slot in a pool's recent blocks"
git tag ch54
```

## Next up

An opt-in per-epoch stake history (local-state-query) to chart stake over time.
