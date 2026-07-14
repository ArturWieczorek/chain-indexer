# Chapter 31 - Tokens

> **Goal:** a tokens section - list the native assets in circulation and a
> per-asset page with total quantity and holder count - completing the last of the
> cardanoscan top-level sections.

We have indexed native assets on outputs since chapter 04 (`ma_tx_out`). This
chapter turns that into a browsable Tokens section.

## Asset totals from the outputs

The assets list (`/assets`, from chapter 13) already aggregates the native assets
held in unspent outputs. This chapter adds a per-asset detail: total quantity and
how many distinct addresses hold it, keyed by policy id and asset name:

```sql
SELECT SUM(m.quantity) AS qty, COUNT(DISTINCT o.address) AS holders
FROM ma_tx_out m JOIN tx_out o ON o.id = m.tx_out_id
WHERE m.policy_id = ? AND m.asset_name = ? AND o.consumed_by_tx_id IS NULL
```

`store.asset_detail` returns that as an `AssetDetail` (or `None` for an unknown
asset). Because it only counts unspent outputs, spending or minting moves the
totals automatically, and it rolls back with the outputs.

## API and explorer

`/assets/{policy_id}/{asset_name}` serves the detail. The explorer gains a
**Tokens** nav entry: a list of assets (name, policy, quantity), each linking to a
detail page (quantity, holders).

On our cardonnay cluster there are no native tokens, so the list shows an empty
state - but the section is complete and tested, and populates the moment an asset
is minted.

## Test first (red), make it pass (green)

Tests cover `store.asset_detail` (summing an asset across two holders, and `None`
for a missing asset) and the API endpoint (detail plus the 404). `make check`
stays green and fully covered.

## What we built

- `AssetDetail` and `store.asset_detail`.
- `/assets/{policy_id}/{asset_name}` and a Tokens section in the explorer.

With this, the explorer covers the cardanoscan top-level sections: **Blocks,
Epochs, Pools, Governance, Tokens, Accounts, Analytics**, plus the live dashboard -
all on data indexed from a node we follow with a hand-written wire protocol, and
ledger state read with a hand-written local-state-query.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch31): tokens section with per-asset detail"
git tag ch31
```

## Where this leaves the project

Every roadmap feature is shipped. The explorer is a working, cardanoscan-shaped
view over a from-scratch indexer. Natural further work: bech32 asset fingerprints,
richer protocol-parameter and pool-metadata pages, and a Postgres backend for
mainnet-scale volume (design seam three from chapter 18).
