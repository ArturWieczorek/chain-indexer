# Chapter 33 - Clickable governance and epoch blocks

> **Goal:** make the explorer navigable the way a real explorer is - every id is a
> link that leads somewhere. This chapter adds a DRep detail page, links each
> governance vote back to its voter and its action, lists an epoch's blocks, and
> fixes a routing bug that made governance actions un-clickable.

The explorer had the data but not the links. A DRep was plain text; a governance
action id could not even be opened; an epoch page showed counts but not the blocks
themselves. This chapter closes those gaps.

## The routing bug: a `#` in the id

A governance action has no id of its own - it is `txid#index` (chapter 32). That
`#` is also the character a browser uses to start a URL fragment, so a link like
`#/gov/<txid>#0` broke in two ways: the router saw a second fragment, and the
`fetch` to `/governance/actions/<txid>#0` was truncated at the `#`, so the server
looked up `<txid>` (no index) and returned 404.

The fix is to encode the id wherever it crosses a URL boundary:

- `link()` builds the href with `encodeURIComponent(id)`, so `#` becomes `%23`.
- The router decodes each path segment (`safeDecode`) back to the real id.
- API calls that interpolate an id encode it again for the request path.

With that, `<txid>#0` survives the round trip and the action opens.

## DRep detail

`/governance/dreps/{drep_id}` now returns, alongside the deposit and vote count,
the votes the DRep cast: each is a `DRepVote` (`gov_action_id`, `action_type`,
`vote`). The store joins `voting_procedure` to `gov_action_proposal` on the action
id; a vote that refers to an action we have not indexed shows its type as
`Unknown` rather than dropping the row. The explorer gets a DRep page listing
those votes, each linking to the action, and the governance page's DRep rows and a
governance action's DRep voters now link to it.

## Epoch blocks

`/epochs/{epoch_no}/blocks` returns the blocks in an epoch (newest first), reusing
the same block shape as the block list. An epoch is `slot_no / epoch_length`, so
the query is a single range filter. The epoch page now lists those blocks, each
clickable through to the block, its height, and its slot.

## Test first (red), make it pass (green)

Store tests cover `drep_votes` (resolving the action type and marking an unindexed
action `Unknown`) and `blocks_in_epoch` (newest-first ordering, empty for an epoch
with no blocks). API tests cover the DRep detail votes payload and the epoch-blocks
endpoint (including the 404 when no network params are configured). `make check`
stays green and fully covered.

## What we built

- `DRepVote` model; `store.drep_votes` and `store.blocks_in_epoch`.
- `/governance/dreps/{drep_id}` votes payload and `/epochs/{epoch_no}/blocks`.
- Explorer: id-safe routing (`encodeURIComponent` + `safeDecode`), a DRep detail
  page, DRep links from the governance page and from a vote's voter, and a
  clickable block list on the epoch page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch33): clickable DRep pages, epoch blocks, and id-safe routing"
git tag ch33
```

## Next up

More cardanoscan-shaped surface: a certificates browser (all certificate types), a
transaction detail with Summary / UTXOs / Metadata tabs, and governance sub-pages
(committee, protocol parameters, ADA pots).
