# Chapter 67 - Datums by hash

> **Goal:** index each output's datum **hash** and answer `GET /datums/{hash}` -
> the second thing [kupo](https://github.com/CardanoSolutions/kupo) returns that we
> did not yet expose.

## Why split datums from scripts

The plan paired "datums and reference scripts" in one chapter. They are split here
on purpose. A **datum hash is unambiguous**: it is the blake2b-256 of the datum's
CBOR bytes, and for an inline datum those are exactly the bytes we already keep
(chapter 47) - so the hash matches the chain by construction, no fixture needed. A
**script hash** is fiddlier (blake2b-224 over a language-prefixed serialization) and
deserves a real captured script to verify against, so it gets its own next chapter.
Shipping the verifiable half now keeps to the project's "never guess a hash" rule.

## What we added

An output can carry a datum two ways (the Conway `datum_option`, output map key 2):

- `[1, CBORTag(24, datum_bytes)]` - an **inline** datum. We keep its bytes; its hash
  is `blake2b-256(datum_bytes)`.
- `[0, datum_hash]` - a **by-reference** hash. We keep the hash, but the datum
  itself lives elsewhere (a witness), so we have no preimage for it.

`cbor_blocks._datum_option` now returns both `(inline_datum_hex, datum_hash_hex)` for
either form. `TxOut` gains a `datum_hash` field; migration 19 adds `tx_out.datum_hash`
(indexed); `OutputIndexer` stores it. It rides on outputs everywhere they are read
(address UTxOs, transaction pages, and the `/matches` results from chapter 64).

The lookup, `store.get_datum(hash)`, returns the datum bytes for any hash we have
seen **inline**; a by-reference hash we have never seen inline is a `404`. The
endpoint is `GET /datums/{hash}`.

## Test first (red), make it pass (green)

`test_cbor_blocks.py` checks the inline hash equals `blake2b-256` of the datum bytes
and that a by-reference hash is kept without a preimage. `test_store.py` and
`test_api.py` cover `get_datum` / `/datums/{hash}` (hit and miss). `make check` stays
green at 100 percent.

## What we built

- `cbor_blocks._datum_option` (inline datum + hash, both forms); `TxOut.datum_hash`.
- Migration 19 `tx_out.datum_hash`; `OutputIndexer` writes it; outputs and matches
  expose it.
- `store.get_datum` and `GET /datums/{hash}`.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch67): index datum hashes and serve datums by hash"
git tag ch67
```

## Next

Reference scripts: index the output's script reference (key 3) and serve
`GET /scripts/{hash}`, verifying the script hash byte-for-byte against a real one.
