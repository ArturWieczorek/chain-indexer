# Chapter 27 - Account links in the UI

> **Goal:** make stake accounts reachable by clicking, not just by pasting a stake
> address. Link a pool's reward address and its delegators to their account pages.

Chapter 26 added account pages, but the only way to reach one was to type a
`stake_test1...` address into the search box. That is a dead end for browsing.
Real explorers link *to* accounts from everywhere a stake address appears. This
short chapter adds the two most useful links, both on the pool page.

## Two new links

- **Reward address**: every pool registration names a reward account (a stake
  address). We already store it; now the API returns it in bech32
  (`stake_test1...`) and the explorer renders it as a link to that account.
- **Delegators**: a new `store.pool_delegators` returns the stake credentials
  whose *latest* delegation is to this pool (a redelegation moves a delegator to
  the new pool, so the list stays current). The pool detail page lists them, each
  a link to its account.

## Turning a credential into a stake address

Delegators are stored as 28-byte credentials. A stake address is a 1-byte header
plus that credential, so to display and link a credential we prepend the testnet
stake-key header (`0xe0`) and bech32-encode it (chapter 25). The account route
already decodes a `stake_test1...` back to the credential, so the round trip just
works. A non-hex id (test data) passes through unchanged.

## Test first (red), make it pass (green)

Tests cover `store.pool_delegators` (including that a redelegation drops a
delegator from the old pool), and that `/pools/{id}` returns a bech32 reward
address and a list of `stake_test1...` delegator links. `make check` stays green
and fully covered.

## What we built

- `store.pool_delegators` and the `_stake_display` helper.
- `/pools/{id}` returning a bech32 reward address and a `delegators_list`.
- Clickable reward-address and delegator links on the pool page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch27): link accounts from the pool page"
git tag ch27
```

## Next up

Further parity: controlled stake on accounts, an analytics/charts page, token
pages, and richer transaction pages.
