# Chapter 36 - Policy pages and readable asset names

> **Goal:** make an asset's policy a link to a page of its own, listing every
> asset minted under that policy, and show human-readable asset names alongside
> their hex.

An asset page showed the policy id as plain text, and asset names only as hex. A
policy is a meaningful entity - one minting policy can mint many assets - so it
deserves a page, and a name like `436861696e4964784e4654` is much friendlier read
as `ChainIdxNFT`.

## Grouping assets by policy

`store.policy_detail(policy_id)` sums each asset under a policy from the unspent
outputs (the same `ma_tx_out` join the asset list uses), grouped by asset name, and
returns a `PolicyDetail` (the policy id, the asset count, and an `AssetDetail` per
asset). It returns `None` when the policy has minted nothing we hold, which the API
turns into a 404.

## Readable names

An asset name on-chain is raw bytes, carried as hex. `_asset_name_text` decodes it
as UTF-8 and returns the text only when it is printable, otherwise `""`. So a
minted `ChainIdxNFT` reads as text, while a binary or non-UTF-8 name falls back to
its hex without ever raising. The asset and policy responses carry both
`asset_name` (hex) and `asset_name_text`.

## API and explorer

- `/policies/{policy_id}` returns the policy's asset count and its assets.
- `/assets/{policy_id}/{asset_name}` now also returns `asset_name_text`.
- In the explorer, the policy id on an asset page and in the Tokens list links to
  a **Minting policy** page listing every asset under it (each linking back to its
  asset page), and asset names show their decoded text next to the hex.

## Test first (red), make it pass (green)

A store test groups two assets under one policy and checks the count and the
`None` for an unknown policy. API tests cover `_asset_name_text` (a real name, a
non-UTF-8 byte, a control byte, and invalid hex), the `asset_name_text` field, and
the policy endpoint plus its 404. `make check` stays green and fully covered.

## What we built

- `PolicyDetail` model; `store.policy_detail`.
- `_asset_name_text`; `asset_name_text` on asset responses; `/policies/{policy_id}`.
- A Minting policy page, policy links from the asset and Tokens pages, and
  decoded asset names in the UI.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch36): per-policy pages and readable asset names"
git tag ch36
```

## Next up

Governance sub-pages: a committee view (which also gives committee voters a page),
protocol parameters, and ADA pots, backed by new local-state queries.
