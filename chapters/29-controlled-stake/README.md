# Chapter 29 - Controlled stake

> **Goal:** show how much ada an account controls, not just its rewards. Index the
> stake part of each output address so we can total the unspent value behind a
> stake credential.

An account page already shows delegation and rewards (chapter 26). Cardanoscan also
shows **controlled stake**: the total ada in every address that shares this stake
credential. That is derivable from the outputs we already index, once we record
which stake credential each output belongs to.

## The stake part of an address

A Cardano **base address** is 57 bytes: a 1-byte header, a 28-byte payment
credential, and a 28-byte **stake credential**. Two addresses with different
payment parts but the same stake part belong to the same account - that shared
stake credential is what stake and rewards are reckoned against.

`stake_credential_of(address)` pulls bytes 29..57 out of a base address (and
returns `None` for enterprise/pointer addresses, which have no stake part, and for
non-hex test ids). The output indexer computes it and stores it in a new
`stake_cred` column (migration 8).

## Controlled stake is one sum

With that column, controlled stake is the same shape as an address balance, keyed
by the stake credential instead of the full address:

```sql
SELECT SUM(lovelace) FROM tx_out
WHERE stake_cred = ? AND consumed_by_tx_id IS NULL
```

`store.controlled_stake(credential)` runs it. Spending an output clears its
`consumed_by_tx_id` (chapter 04), so it drops out of the total automatically, and
because `stake_cred` lives on the block-keyed `tx_out` row it rolls back for free.

## API and explorer

`/accounts/{stake}` gains a `controlled_stake` field, and the account page shows it
alongside delegation and rewards. Now an account page answers the three questions
that matter: who it delegates to, how much stake it controls, and what rewards it
has earned.

## Test first (red), make it pass (green)

Tests cover `stake_credential_of` (a real base address, a non-hex id, a
wrong-length value) and `store.controlled_stake` (summing unspent outputs by stake
credential, dropping to zero when spent), plus the API field. `make check` stays
green and fully covered.

## What we built

- `stake_credential_of` and a `stake_cred` column on `tx_out` (migration 8).
- `store.controlled_stake` and a `controlled_stake` field on account pages.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch29): controlled stake on account pages"
git tag ch29
```

## Next up

[Chapter 30 - Analytics](../30-analytics/): a charts page - transactions per epoch
over time - rendered as inline SVG in the explorer, no chart library.
