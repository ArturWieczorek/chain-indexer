# Chapter 47 - CIP-68 asset metadata

> **Goal:** read CIP-68 metadata, which - unlike CIP-25 - does not live in
> transaction metadata but in an **inline datum** on a reference output. So this
> chapter teaches the indexer to capture datums.

## How CIP-68 differs

CIP-25 metadata rides in the mint transaction's metadata (chapter 46). CIP-68 instead
splits a token in two (CIP-67 name prefixes):

- a **reference token** named with the `(100)` prefix (`000643b0...`), held in a
  UTxO whose **inline datum** carries the metadata, and
- a **user token** named with `(222)` (NFT, `000de140...`) or `(333)` (FT,
  `0014df10...`), the one that actually circulates.

To read a user token's metadata you find its reference token and decode that
output's datum. The datum is a Plutus constructor (`CBOR tag 121`) whose first
field is the metadata map.

## Indexing datums

The output decoder now reads an output's inline datum (Conway map key 2 =
`[1, CBORTag(24, bytes)]`) into `TxOut.datum`, and the `OutputIndexer` stores it in
a new `tx_out.datum` column (migration 14). Because it hangs off `tx_out`, it rolls
back with the output.

`decode_cip68_datum` turns a datum into a plain metadata dict, rendering byte
strings as text when printable (else hex) and recursing into lists and maps.
`reference_asset_name` maps a user token name to its reference token name by
swapping the CIP-67 prefix.

`store.cip68_metadata(policy, asset_name)` resolves a user token: find the
reference token's unspent output with a datum, decode it. `/assets/{policy}/{name}`
returns CIP-25 metadata when present, otherwise CIP-68, tagging which with a
`metadata_standard` field; the explorer's metadata panel names the standard.

## Test first (red), make it pass (green)

Decoder tests cover the reference-name mapping, inline-datum extraction (map form,
datum hash, none, legacy list), and decoding a datum with every leaf kind (text,
non-UTF-8 and non-printable bytes to hex, list, nested map). An API test mints a
reference/user pair and checks the user token resolves its metadata, plus the
cases with no reference, a non-user token, and a datum carrying no metadata map.
`make check` stays green and fully covered.

## What we built

- `TxOut.datum`, inline-datum decoding, `decode_cip68_datum`,
  `reference_asset_name`, and the CIP-67 label constants in `cbor_blocks`.
- Migration 14 (`tx_out.datum`); `OutputIndexer` stores datums;
  `store.cip68_metadata`.
- CIP-68 fallback in `/assets/{policy}/{name}` with a `metadata_standard` field,
  shown on the asset page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch47): read CIP-68 asset metadata from inline datums"
git tag ch47
```

## Where this leaves the project

Both token-metadata standards are covered: CIP-25 from transaction metadata and
CIP-68 from inline datums (which also gives the indexer datum awareness to build
on). The project speaks all five node-to-client mini-protocols and presents a
cardanoscan-shaped explorer over a from-scratch, reorg-aware indexer.
