# Chapter 22 - Pools

> **Goal:** a proper Pools section. Index which pool minted each block, then build
> pool pages that combine registration parameters with blocks-minted and delegator
> counts - the core of what cardanoscan's pool pages show.

We already index pool *registrations* (chapter 06). But an explorer's pool page
answers more: how many blocks has this pool made, and how many people delegate to
it? Both are derivable from data we already have, once we index one more thing:
the block's **issuer**.

## Who minted the block?

Every block header is signed by the pool that made it, and the header carries the
pool's issuer verification key. The pool's id is the blake2b-224 hash of that key:

```
  pool_id = blake2b_224(header.issuer_vkey)
```

We confirmed this against the live node: hashing the issuer key of 40 recent
blocks produced exactly the three registered pool ids, every time. So we compute
the issuer while decoding a block (both the CBOR path and the Ogmios path, which
carries `issuer.verificationKey`) and store it on the block row (migration 5 adds
an `issuer` column). Counting blocks per issuer then gives blocks-minted per pool.

## Delegator counts

A pool's delegators are the stake addresses whose *most recent* delegation is to
that pool. We already index delegation certificates (chapter 06), and `tx_id` is a
global, chain-ordered counter, so "most recent" is "highest `tx_id`":

```sql
SELECT COUNT(*) FROM delegation d WHERE d.pool_id = ?
  AND d.tx_id = (SELECT MAX(tx_id) FROM delegation d2 WHERE d2.addr = d.addr)
```

That counts each address once, for whichever pool it last delegated to - so a
redelegation moves the delegator from the old pool to the new one, exactly as it
should.

## Pool pages

`store.pool_summaries()` and `store.pool_detail(pool_id)` return a `PoolSummary`
per active pool: pool id, blocks minted, delegators, and pledge / margin / reward
address from the latest registration. The API serves them at `/pools` (list) and
`/pools/{id}` (detail, plus the pool's recent block hashes), and the explorer gains
a **Pools** nav entry with a list page (pool, blocks, delegators, pledge, margin)
and a detail page.

> **Live stake is next, not here.** cardanoscan also shows a pool's *live stake*
> and *saturation*. Those are ledger state - they come from chapter 20's
> local-state-query, not from the blocks - so wiring them into pool pages (which
> needs persisting a stake snapshot) is its own step. This chapter delivers
> everything derivable from the indexed chain; live stake follows.

## Test first (red), make it pass (green)

Tests cover the issuer computation on both a real CBOR block and a real Ogmios
block (both hash to the pool that actually minted block 33), the store's pool
summaries and detail (blocks minted, delegators, params, recent blocks, and the
`None` for an unknown pool), and the `/pools` and `/pools/{id}` endpoints. `make
check` stays green and fully covered.

## What we built

- Block `issuer` (the minting pool id): computed in the CBOR and Ogmios decoders,
  stored via migration 5.
- `PoolSummary` and `store.pool_summaries` / `pool_detail` /
  `recent_blocks_by_pool`, with delegator counting by latest delegation.
- API `/pools` and `/pools/{id}`; a Pools section in the explorer.

## Glossary

- **Block issuer**: the pool that produced a block; its id is the hash of the
  header's issuer key.
- **Delegators**: stake addresses whose most recent delegation points at a pool.
- **Pledge / margin**: the pool operator's staked commitment and the fee fraction
  they take, from the registration certificate.
- **Live stake / saturation**: ledger-state metrics (via local-state-query) added
  in a later chapter.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch22): index block issuers and add pool pages"
git tag ch22
```

## Next up

[Chapter 23 - Accounts and rewards](../23-accounts/): stake-account pages -
delegation, controlled stake, and rewards - using local-state-query's reward and
account queries, and surfacing live stake on the pool pages.
