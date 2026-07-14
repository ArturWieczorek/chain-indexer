# Chapter 46 - CIP-25 asset metadata

> **Goal:** show an NFT's name, image, and description - its CIP-25 metadata -
> on the asset page. It builds directly on the transaction metadata we already
> decode, so it needs no new node query and no new storage backend.

## Where CIP-25 lives

CIP-25 puts NFT metadata in the **transaction metadata** under label **721**:

```
{ 721: { policy_id: { asset_name: { name, image, description, ... } }, version } }
```

We already decode transaction metadata to JSON (chapter 35). So this chapter reads
label 721 out of the mint transaction's metadata and stores it per asset.

## Indexing it

`AssetMetadataIndexer` parses `tx.metadata` for label 721 and writes one row per
asset into `asset_metadata` (migration 13), keyed by policy id and by the asset
name **in hex** (CIP-25 keys assets by their UTF-8 name; we hex it to match how
asset names are stored everywhere else). The optional `version` entry is skipped.
The table is block-keyed, so it rolls back with the mint.

`store.asset_metadata(policy_id, asset_name)` returns the stored JSON (or `None`),
and `/assets/{policy_id}/{asset_name}` now carries a `metadata` field. The explorer
shows a **Metadata (CIP-25)** panel on the asset page - each field, with nested
objects (files, traits) rendered as JSON.

## Test first (red), make it pass (green)

An API test mints an asset with a 721 block (including a `version` entry and a
nested `files` array), and a couple of transactions with non-721 metadata and no
metadata at all, then checks the asset's metadata comes back and that an asset
minted without CIP-25 reports `null`. `make check` stays green and fully covered.

## What we built

- Migration 13 `asset_metadata`; `AssetMetadataIndexer`; `store.asset_metadata`.
- `metadata` on `/assets/{policy_id}/{asset_name}` and a CIP-25 panel on the asset
  page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch46): index and show CIP-25 asset metadata"
git tag ch46
```

## Next up

CIP-68 metadata, which lives in an inline datum on a reference output rather than
in transaction metadata - so it needs us to start indexing datums.
