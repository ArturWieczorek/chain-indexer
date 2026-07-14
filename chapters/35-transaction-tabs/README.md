# Chapter 35 - Transaction detail tabs

> **Goal:** turn the flat transaction page into a tabbed detail like a real
> explorer: **Summary**, **UTXOs**, and **Metadata**. Along the way, resolve each
> input to the value it spends, decode the fee, and index transaction metadata.

The transaction page listed input references and output addresses, but not what an
input was worth, nor the fee, nor any metadata. This chapter fills those in.

## Resolving inputs

An input only names an earlier output: a transaction id and an output index. To
show what it spends, we look that output up in `tx_out` (joining through `tx` on
the hash) and copy its address, lovelace, and assets into a `ResolvedInput`. If we
never indexed that output - a genesis or faucet UTxO, or one from before our sync
start - the reference stays, but the value is zero and `resolved` is false. The
explorer then shows it plainly instead of linking to a page that does not exist,
which is why clicking a genesis input no longer dead-ends in a 404.

## Fee and metadata

Two more transaction-body fields join the decode:

- **fee** is body key 2, a plain coin.
- **metadata** lives in the block's auxiliary-data map (`{tx_index -> aux}`), read
  right after the transaction bodies. Auxiliary data has three era shapes - a bare
  metadata map (Shelley), a `[metadata, scripts]` pair (Shelley-MA), and a tag-259
  map whose key 0 is the metadata (Alonzo onward) - and `_extract_metadata` reaches
  the metadata map in each. `_metadatum_to_json` renders it JSON-friendly: bytes
  become hex, maps and lists recurse, and map keys are stringified. (cbor2 hands
  nested maps back as `frozendict`, so the checks match `Mapping`, not `dict`.)

Migration 10 adds `fee` and `metadata` columns to `tx`; both default for rows
written before the migration, so a re-index is what populates them.

## The tabs

`/txs/{hash}` now returns the fee, the parsed metadata (or null), resolved inputs,
and outputs with their assets. Certificates come back as structured records (from
the chapter 34 table) rather than strings, so the explorer can link each subject.
The explorer renders three tabs, addressable as `#/tx/{hash}/summary|utxos|metadata`:

- **Summary**: id, block, fee, total output, input/output counts, and the
  certificates (linked), proposals, and votes the transaction carried.
- **UTXOs**: inputs (source, address, value, assets) and outputs (address, value,
  assets), with unresolved inputs shown without a link.
- **Metadata**: each metadata label and its value, or an empty state.

## Test first (red), make it pass (green)

Decoder tests cover the metadata helpers across all three era shapes (plus the
empty cases) and decode a crafted block end to end, checking the fee and metadata
come through. API tests check the resolved input value and assets, the fee and
parsed metadata, structured certificates, and the unresolved-input path. `make
check` stays green and fully covered.

## What we built

- `ResolvedInput` model; `Tx.fee`/`Tx.metadata`; `TxDetail` carrying fee, metadata,
  resolved inputs, and asset-bearing outputs.
- Fee and metadata decoding in `cbor_blocks` (`_extract_metadata`,
  `_metadatum_to_json`, `_metadata_json`), read from the block's auxiliary data.
- Migration 10 (`tx.fee`, `tx.metadata`); `store.get_tx` resolving inputs and
  loading assets; `store.certificates_for_tx`.
- A tabbed transaction page (Summary / UTXOs / Metadata) with linked certificates
  and a home-page tx count that links through to the block's transactions.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch35): tabbed transaction detail with resolved inputs, fee, and metadata"
git tag ch35
```

## Next up

An asset's policy becomes a link to a per-policy page, then governance sub-pages
(committee, protocol parameters, ADA pots) backed by new local-state queries.
