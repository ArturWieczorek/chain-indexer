# Chapter 64 - A matches API (kupo-style watch patterns)

> **Goal:** answer the question [kupo](https://github.com/CardanoSolutions/kupo)
> answers - "give me the outputs matching this pattern" - without kupo's storage
> engine, because we already index every output.

## The idea

kupo is a focused chain-index: you give it **patterns** (an address, a policy id, a
wildcard) and it tracks only the matching outputs, then serves them over a small
HTTP API - each with its value, datum, and whether it has been spent. We already
store every output, with exactly those columns:

- `tx_out(address, lovelace, datum, consumed_by_tx_id)` - the value, the inline
  datum, and (`consumed_by_tx_id IS NULL`) the unspent flag;
- `ma_tx_out(policy_id, asset_name, quantity)` - the native assets;
- `tx.hash` + `tx_out.index_no` - the output reference kupo returns.

So we do not need a new index. We need only to turn a pattern string into a query
over the index we have.

## What a pattern is

`patterns.py` is pure - it just classifies a string into a `Pattern`:

- `*` - everything;
- a bech32 **address** (`addr...`) or raw hex - matched against `tx_out.address`;
- a bech32 **stake address** (`stake...`) - matched against `tx_out.stake_cred`, so
  "every UTxO delegating to this stake key" (a base address is a 1-byte header plus
  the 28-byte credential, so we drop the header);
- a **policy id** (56 hex characters) - outputs holding any asset of that policy;
- `<policyid>.<assetname>` - outputs holding that one asset.

Because the parser only decodes and classifies (bech32 is reused from
`bech32.py`), it is unit-tested on its own, with no database.

## The query

`store.matches(pattern, spent)` builds one `SELECT` over `tx_out` (joined to
`ma_tx_out` for the policy/asset patterns), choosing a fixed `WHERE` fragment per
pattern kind and binding every value as a parameter. `spent` is `"unspent"` (the
default, kupo's common case), `"spent"`, or `"all"`. It returns `MatchRecord`s - the
output reference, address, value, assets, datum, and spent flag. Because it is a
`Store` method, it runs on SQLite and Postgres alike.

The endpoint `GET /matches/{pattern}?spent=` serves it in a kupo-shaped JSON:

```
GET /matches/addr_test1.../             # a wallet's UTxOs
GET /matches/<policyid>                 # every output holding that policy's assets
GET /matches/<policyid>.<assetname>     # a single asset's location
GET /matches/*?spent=all                # the whole output set, spent and unspent
```

## Test first (red), make it pass (green)

`test_patterns.py` pins the parser against bech32 values it encodes itself.
`test_store.py` builds a block with one spent and two unspent outputs and checks
every pattern kind and every `spent` filter. `test_api.py` drives the endpoint,
including the `422` on a bad `spent` value. `make check` stays green at 100 percent.

## What we built

- `patterns.py`: `Pattern` + `parse_pattern` (pure).
- `store.matches` + a `MatchRecord` model; the `Store` interface gains one method.
- `GET /matches/{pattern}` in the API.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch64): a kupo-style matches API over the existing index"
git tag ch64
```

## Where this leaves the project

The indexer can now be *queried like kupo* - point a pattern at it and get the
matching UTxOs - reusing the index we already keep. The next chapter fills in the
two things kupo returns that we do not yet store: an output's datum **hash** and its
**reference script**.
