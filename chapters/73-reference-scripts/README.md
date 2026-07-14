# Chapter 73 - Reference scripts (/scripts/{hash})

> **Goal:** index an output's reference script and serve it by hash, kupo-style -
> the last piece of the kupo half, and the one that needed a real script to get the
> hash byte-exact.

## Why this waited

A datum hash (chapter 67) is unambiguous - the blake2b-256 of the datum bytes. A
**script hash** is trickier: it is `blake2b-224(language_byte || serialized_script)`,
and getting the serialization exactly right (which bytes, for native versus Plutus)
is the kind of thing that is easy to get subtly wrong. So this chapter was held back
until the rule could be checked against real scripts, rather than guessed.

## Verified against real scripts

The rule is pinned against two real scripts whose hashes are known independently
(a script's hash is the payment credential of its address, and a native policy's
hash is its policy id):

- a **Plutus V3** script hashing to `bb7d4c3f...` (from its `addr_test1w...` address);
- a **native** `all [ sig, before ]` script hashing to `8324eb97...` (its policy id).

Both match, so the test asserts the real hashes, not plausible-looking ones - the
same standard as the block and transaction identity tests.

## What it does

The reference script sits in the Conway output map at key 3, as
`#6.24(bytes .cbor script)` where `script = [tag, body]` (tag 0 native, 1/2/3 Plutus
V1/V2/V3). `cbor_blocks._reference_script` computes the hash:

- **native:** `blake2b-224(0x00 || the script term's original CBOR bytes)` - taken
  byte-for-byte from the wrapper (no re-encoding), so a non-canonical script still
  hashes correctly;
- **Plutus:** `blake2b-224(langbyte || the raw script bytes)`.

`TxOut` gains `reference_script_hash` / `reference_script_type` /
`reference_script`; migration 20 adds the columns; `OutputIndexer` writes them; and
`store.get_script(hash)` backs `GET /scripts/{hash}` (returning the language and
CBOR, or a 404). Outputs now also carry `reference_script_hash` wherever they are
listed.

## Test first (red), make it pass (green)

`test_cbor_blocks.py` asserts the two real hashes and covers the malformed shapes
(no key 3, not a tag 24, bad CBOR, unknown tag, non-bytes Plutus body).
`test_store.py` and `test_api.py` cover `get_script` and `/scripts/{hash}` (hit and
404). `make check` stays green at 100 percent.

## What we built

- `cbor_blocks._reference_script` (byte-exact hash, verified against real scripts).
- `TxOut` reference-script fields; migration 20; `OutputIndexer` writes them.
- `store.get_script` and `GET /scripts/{hash}`; outputs expose the hash.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch73): index reference scripts and serve them by hash"
git tag ch73
```

## Where this leaves the kupo + adder work

Complete. kupo-style querying: `/matches` patterns, datums by hash, and now scripts
by hash. adder-style pushing: rich filtered events to webhooks, rollbacks included.
All over the one index and the one event bus the project already had.
