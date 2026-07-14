# Chapter 25 - Bech32 addresses

> **Goal:** show ids the way everyone reads them - `pool1...`, `addr_test1...`,
> `stake_test1...` - instead of raw hex. This is the single change that makes the
> explorer look like a real one, and it makes addresses and pools searchable by
> their familiar form.

We have been storing and displaying raw hex: a pool as `6887684e...`, an address
as `00fe75e6...`. Cardano tools show **bech32** instead. This chapter adds bech32
encoding and decoding and threads it through the API, so the explorer's ids match
what you would paste from a wallet or see on cardanoscan.

## What bech32 is

Bech32 (BIP-0173, which Bitcoin also uses) encodes bytes as: a human-readable
prefix that says what the thing is (`pool`, `addr`, `stake`), the separator `1`,
then the data plus a 6-character checksum, all in a 32-symbol alphabet. The
checksum catches typos. Cardano picks the prefix by context, and for addresses the
network too: mainnet is `addr` / `stake`, testnet is `addr_test` / `stake_test`.

The algorithm is small and pure - a checksum polynomial and an 8-bit-to-5-bit
regrouping - which makes it a perfect test-first module.

## Getting it right, not close

Bech32 is exact: one wrong bit and the checksum fails. So we did not trust a
from-memory implementation - we generated ground-truth values with the real tools
and tested against them:

```text
$ cardano-cli query stake-pools           # gives pool1... ids
$ echo 6887684e...21a0 | bech32 pool       # -> pool1dzrksnnq5vdl38w2uk6...
$ echo 00fe75e6...be825 | bech32 addr_test # -> addr_test1qrl8tejnp9jn4z...
```

The tests assert our `pool_to_bech32` and `address_to_bech32` reproduce those
exact strings, and that decoding round-trips back to the original bytes. The
address prefix is chosen from the header byte (high nibble = type, low nibble =
network), covered for payment and stake, testnet and mainnet.

## Threading it through the API

Encoding is for display; decoding is for lookups. So:

- pool ids, block issuers, and output addresses are returned in bech32;
- the `/pools/{id}` and `/addresses/{addr}` routes accept a bech32 argument and
  decode it back to hex before querying the store.

Two small helpers keep this safe: `_pool_display` / `_address_display` fall back to
the original string if it is not decodable hex (so the synthetic ids in tests, and
anything unexpected, pass through untouched), and `_to_hex` decodes a prefixed
argument or leaves a plain one alone. The store still keys everything by hex; only
the surface changes.

## The explorer, suddenly legible

With the API emitting bech32, the explorer now shows `pool1...` in the pools table,
`addr_test1...` on transaction outputs, and a "minted by" link on each block to the
pool that made it. The search box accepts `pool1...` (and still block heights,
slots, hashes, and addresses). No client-side changes were needed beyond routing a
`pool1...` search - the ids just arrive readable.

## Test first (red), make it pass (green)

Tests cover the encoder against the exact cardano-cli values, decoding round-trips,
the header-to-prefix logic for all four payment/stake and testnet/mainnet cases,
arbitrary-byte round-tripping, and the three decode error paths (no separator,
bad character, bad checksum), plus the API display/decode helpers. `make check`
stays green and fully covered.

## What we built

- `chainidx.bech32`: `encode` / `decode` and `pool_to_bech32` /
  `address_to_bech32`, verified against cardano-cli.
- API ids and addresses rendered in bech32, with routes that accept bech32 and
  decode it for lookups.
- The explorer showing `pool1...` / `addr_test1...` and a block's minting pool.

## Glossary

- **Bech32**: a checksummed text encoding of bytes with a human-readable prefix.
- **HRP (human-readable prefix)**: the `pool` / `addr` / `stake` part before the
  `1`.
- **Header byte**: an address's first byte; its nibbles give the address type and
  the network.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch25): bech32 addresses and pool ids"
git tag ch25
```

## Next up

[Chapter 26 - Accounts and rewards](../26-accounts/): now that stake addresses are
human-readable, stake-account pages - delegation, controlled stake, and rewards -
using local-state-query's account and reward queries.
