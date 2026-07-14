# Chapter 50 - Full pool on-chain details

> **Goal:** round out the pool page with the rest of the registration
> certificate - VRF key hash, owners, relays, metadata hash, and when it
> registered - plus a small performance summary. Everything here is on-chain; the
> reward-based panels a full explorer shows are deliberately left out (see below).

## The rest of the certificate

A pool registration carries more than pledge/cost/margin. The decoder now also
reads the **VRF key hash** (`cert[2]`), the **owners** (`cert[7]`, stake key
hashes), the **relays** (`cert[8]`, rendered as `host[:port]` / DNS strings by
`_decode_relay`), and the **metadata hash** (`cert[9][1]`). Migration 17 stores
them on `pool_registration` (owners and relays as JSON arrays), and `_pool_summary`
reads them back, joining `block` to learn the **registration slot** so the API can
report when the pool registered.

`PoolSummary` gains `vrf_hash`, `metadata_hash`, `owners`, `relays`, and
`registered_slot`; `/pools/{id}` returns them (owners as `stake_test1...`
addresses, the hex pool id alongside the bech32 one, and a `registered_time` when
network parameters are configured). The pool page lays them out like a
professional explorer's "On-chain details", and adds a small **Performance** panel:
lifetime blocks, epochs minting, and average blocks per epoch, above the
blocks-per-epoch chart.

## What is deliberately not here

A full explorer also shows an **epoch trend** and **rewards per epoch** (active
stake, pool/delegator rewards, ROS). Those are outputs of the ledger's reward
calculation across epoch boundaries - not carried in blocks by any protocol, and
not something we recompute. We surface only what the chain actually records; the
honest way to add the rewards history later is to snapshot the node's own values
via local-state-query once per epoch and accumulate, never to fabricate them.

## Test first (red), make it pass (green)

A decoder test reads the VRF hash, owners, all three relay shapes, and the
metadata hash from a registration cert (and the null-anchor case). An API test
registers a pool with these fields and checks the hex id, VRF hash, metadata hash,
owners (as stake addresses), relays, and that a registration time is derived.
`make check` stays green and fully covered.

## What we built

- `_decode_relay` and full pool-registration decoding (VRF, owners, relays,
  metadata hash); `PoolRegistration`/`PoolSummary` fields; migration 17.
- `/pools/{id}` returns the full on-chain details and a registration time; the pool
  page shows them plus a performance summary.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch50): full pool on-chain details (vrf, owners, relays, metadata, registered)"
git tag ch50
```

## Next up

Fetching off-chain metadata behind configuration, image rendering, and UI polish
(favicons, theme and colour selection).
