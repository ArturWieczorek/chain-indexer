# Chapter 58 - A configuration file

> **Goal:** replace the scattering of environment variables with one JSON config,
> like cardano-db-sync's, that says where the node and database are and which
> optional features (indexers) are on. Environment variables still work and take
> precedence, so nothing breaks.

## One place for settings and feature switches

`config.py` defines a `Config` value: `socket_path`, `network_magic`,
`genesis_path`, `db_path`, the opt-in extras (`fetch_metadata`, `ipfs_gateway`,
`stake_history`), and a set of enabled **features** - the optional indexers
(`certificates`, `governance`, `withdrawals`, `assets`, `mints`). The core output
and input indexers always run; the rest are toggled, the way db-sync's
`insert_options` switch `multi_asset`, `metadata`, `governance`, and so on.

- `from_dict` builds a `Config` from parsed JSON. `features` is a `{name: on}` map;
  a feature not mentioned defaults to on, so an empty map means "everything".
- `load` reads the file at `CHAINIDX_CONFIG` (if any), then layers environment
  variables on top (env wins), so existing env-based runs keep working and a
  one-off override needs no file.

`indexers_for(features)` turns the enabled set into the indexer tuple the store
runs; `default_indexers()` (all features on) is just `indexers_for` of the whole
set, so behaviour is unchanged by default. The live runner now builds everything
from one `Config`.

Example `config.json`:

```json
{
  "socket_path": "/var/.../node.socket",
  "network_magic": 42,
  "genesis_path": "/var/.../shelley/genesis.json",
  "db_path": "chain.db",
  "fetch_metadata": true,
  "ipfs_gateway": "https://ipfs.io/ipfs/",
  "stake_history": true,
  "features": { "governance": true, "mints": false }
}
```

## A note on starting late

Chain-derived data (balances, block counts, certificates) is only complete when
the index is built from origin - intersecting mid-chain leaves inputs to earlier
outputs unresolved and counts short, as with any indexer. Ledger-state read over
local-state-query (live stake, parameters) is correct whenever it is queried, since
it comes from the node's current state, not from replaying blocks.

## Test first (red), make it pass (green)

Tests cover `from_dict` (defaults enabling everything, explicit values and feature
toggles, a non-object `features` guarded), `load` (a file with environment
overrides layered on, and no file at all), and `indexers_for` selecting the core
plus the chosen optional indexers. `make check` stays green and fully covered.

## What we built

- `config.py` (`Config`, `from_dict`, `load`); `indexers.indexers_for` and an
  `OPTIONAL_INDEXERS` registry; the live runner driven by one `Config`.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch58): a JSON config file with feature toggles (env still overrides)"
git tag ch58
```

## Next up

The pool graphs that per-epoch stake history newly makes possible: expected-vs-made
blocks and saturation over epochs.
