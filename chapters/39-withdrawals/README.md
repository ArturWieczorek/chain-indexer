# Chapter 39 - Reward withdrawals

> **Goal:** index reward withdrawals and add a Withdrawals section, the first of
> the remaining cardanoscan blockchain sections. Pure chain data, so it follows
> the same decode-store-serve pattern as certificates.

When a stake account withdraws its staking rewards, the transaction carries a
**withdrawals** field: tx body key 5, a map `{reward_account -> coin}`. We decode
it into `Withdrawal` values (the reward account as hex, and the lovelace amount)
and index them.

## Decode, store, serve

- `_decode_withdrawals` reads tx body key 5 into `Withdrawal`s, wired into
  `_decode_tx` like the other body fields.
- A `WithdrawalIndexer` writes each into a block-keyed `withdrawal` table
  (migration 12), so withdrawals roll back with their block like everything else.
- `store.withdrawals` lists them newest first; `store.withdrawals_for_tx` returns
  the ones a transaction made.

## API and explorer

- `/withdrawals` lists recorded withdrawals, and the transaction detail now
  includes a `withdrawals` array.
- The explorer gains a **Withdrawals** section (reward account, amount,
  transaction), and the transaction Summary tab lists a transaction's
  withdrawals. The reward account is shown as a `stake_test1...` address that
  links to its account page.

## Test first (red), make it pass (green)

A decoder test reads a withdrawal from a body (and the empty case). An API test
covers the empty list, a recorded withdrawal (amount, bech32 reward account, and
transaction), and the withdrawal appearing on the transaction page. `make check`
stays green and fully covered.

## What we built

- `Withdrawal` / `WithdrawalRecord` models; `Tx.withdrawals`; `_decode_withdrawals`.
- `WithdrawalIndexer`; migration 12 `withdrawal` table (rolls back with blocks);
  `store.withdrawals` / `store.withdrawals_for_tx`.
- `/withdrawals`, withdrawals on the transaction page, and a Withdrawals section.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch39): index reward withdrawals and add a Withdrawals section"
git tag ch39
```

## Next up

More blockchain sections: protocol updates and top staking accounts / top
addresses, then richer analytics (time-series charts and a mempool view).
