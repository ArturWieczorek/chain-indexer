# Chapter 40 - Top addresses and staking accounts

> **Goal:** two ranking views - the richest addresses and the largest staking
> accounts - the way an explorer surfaces where the ada is. Aggregate chain data,
> no new node query.

## Ranking from the UTxO set

Both rankings come from `tx_out`, filtered to unspent outputs
(`consumed_by_tx_id IS NULL`):

- `store.top_addresses` groups unspent outputs by address and sums the lovelace,
  richest first.
- `store.top_stake_accounts` groups by the `stake_cred` embedded in each base
  address (the column added in chapter 29) and sums, largest first. Outputs with
  no stake part (enterprise addresses) are excluded.

Both return typed records (`AddressBalance`, `StakeAccountBalance`).

## API and explorer

- `/top/addresses` and `/top/accounts` (each takes a `limit`).
- The Analytics page grows two tables - **Top addresses** and **Top staking
  accounts** - each entry linking to its address or account page. This starts
  filling out the analytics view as well as adding the two ranking sections.

## Test first (red), make it pass (green)

An API test funds a base address (with a stake credential) and a plain address,
then checks that balances are summed per address, ordered richest first, and that
only the base address contributes a staking account. `make check` stays green and
fully covered.

## What we built

- `AddressBalance` / `StakeAccountBalance` models; `store.top_addresses` /
  `store.top_stake_accounts`.
- `/top/addresses` and `/top/accounts`; Top-addresses and Top-staking-accounts
  tables on the Analytics page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch40): top addresses and staking accounts rankings"
git tag ch40
```

## Next up

A Transactions section (a recent-transactions page and recent transactions on the
home page), then richer analytics (time-series charts, and a mempool view built on
the local-tx-monitor mini-protocol).
