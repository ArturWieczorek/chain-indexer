# Chapter 06 - Shelley staking

> **Goal:** index the staking world - stake address registration and delegation,
> and stake pool registration and retirement - as a *new indexer* that plugs into
> the existing pipeline and rolls back for free. And draw the honest line between
> what lives on-chain and what does not.

Cardano's proof-of-stake system runs on **delegation**: ada holders keep their
funds but delegate their *stake* to a **stake pool**, which produces blocks on
their behalf. All of this is announced on-chain through **certificates** carried
inside transactions. That word "carried inside transactions" is the key: it means
the chain-sync stream already contains everything we need. No extra data source.

This is the first chapter that adds a whole new data domain, so it is really a
test of the architecture. If the design from chapters 03 to 05 is right, adding
staking should be almost mechanical. It is.

## The certificates we index

| Certificate | Meaning |
| ----------- | ------- |
| `StakeRegistration` | a stake address announces itself to the ledger |
| `StakeDeregistration` | a stake address retires |
| `StakeDelegation` | a stake address delegates its stake to a pool |
| `PoolRegistration` | a pool registers (or updates) its parameters |
| `PoolRetirement` | a pool schedules its retirement at an epoch |

We model each as a small frozen dataclass and add a `certificates` tuple to `Tx`.
Because Python unions are closed, the type checker forces the indexer to handle
every kind:

```python
Certificate = (
    StakeRegistration | StakeDeregistration | StakeDelegation
    | PoolRegistration | PoolRetirement
)
```

## Three steps, and only three

Adding a data domain now has a fixed recipe:

1. **A new indexer.** `CertIndexer` looks at each transaction's certificates and
   writes a row into the matching table. It only handles the forward direction.
2. **New tables (migration 3).** One per certificate kind, each carrying a
   `block_id` like every other table.
3. **Add the table names to the rollback loop.** We pulled the loop's table list
   out into `_ROLLBACK_TABLES` in the store; adding staking means adding five
   names to it.

That is the entire integration with the reorg engine. There is no staking-specific
rollback code, because there does not need to be: a certificate row carries a
`block_id`, so `rollback_to` already knows how to delete it. The test
`test_staking_certificates_roll_back_with_their_block` proves it - roll back a
block and its pool registration and delegation vanish, while the earlier block's
survive. This is the second design seam (pluggable indexers) and the first
(generic rollback) working together.

## Derived views

From the certificate tables we can answer real questions:

- `pools()` - which pools are registered and not retired.
- `delegation_of(stake_address)` - the pool an address most recently delegated to.
- `is_stake_registered(stake_address)` - whether its latest event was a
  registration.

> **Ordering gotcha, worth internalising.** To decide "latest event" we order by
> `tx_id`, not by each table's own `id`. `tx_id` is the global transaction
> counter, so it increases with chain order across *all* tables. Each table's own
> `id` is a separate sequence - comparing a `stake_registration.id` against a
> `stake_deregistration.id` would be meaningless. Whenever you compare events
> across tables, reach for the shared, chain-ordered key.

## The honest line: on-chain vs ledger state

Here is what we index, and what we deliberately do not:

```
  ON-CHAIN (in tx bodies, we index it)        LEDGER STATE (we do not)
  ------------------------------------        ------------------------
  "alice delegates to pool1"          vs.     "pool1's live stake is 4.2M ada"
  "pool1 registered with 3% margin"           "alice earned 12 ada in rewards"
  "pool1 retires at epoch 5"                   "the epoch stake snapshot"
```

The left column is *declarations* that appear in transactions. The right column
is *computed* by the ledger from the entire history and the protocol's reward
equations; it is not written into any block. cardano-db-sync produces the right
column by querying the node's ledger state through a second mini-protocol
(`local-state-query`). We deliberately do not implement that in v1 (chapter 12
explains the boundary and chapter 18 revisits it). So this project can tell you
*who delegated to whom*, but not *how much they earned*. Stating that boundary
plainly is part of doing the project honestly.

## Test first (red), make it pass (green)

The tests describe pools becoming active and retiring, delegation tracking the
latest pool, registration and deregistration flipping a flag, and certificates
rolling back with their block. `make check` stays green and fully covered.

## What we built

- Five certificate types on `Tx`, and a `CertIndexer` to persist them.
- Migration 3: `stake_registration`, `stake_deregistration`, `delegation`,
  `pool_registration`, `pool_retirement`, all block-keyed.
- `_ROLLBACK_TABLES`, so rollback stays one generic loop.
- Derived views: `pools`, `delegation_of`, `is_stake_registered`.

## Glossary

- **Stake**: the ada whose voting/block-production weight an address controls.
- **Delegation**: assigning your stake to a pool without moving your funds.
- **Stake pool**: a node that produces blocks on behalf of its delegators.
- **Certificate**: an on-chain declaration inside a transaction (registration,
  delegation, and so on).
- **Ledger state**: data the node computes from the whole chain (balances,
  rewards, live stake); not stored in blocks.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch06): index Shelley staking certificates"
git tag ch06
```

## Next up

[Chapter 07 - Conway governance](../07-conway-governance/): the newest layer of
Cardano. We index DReps, votes, and governance action proposals - again as
certificates and fields inside transactions, again riding the same pipeline and
rollback engine.
