# Chapter 26 - Accounts and rewards

> **Goal:** stake-account pages - delegation and reward balance - using the first
> local-state-query that carries an argument: the set of stake credentials to look
> up. Now that stake addresses are `stake_test1...`, accounts are searchable.

Chapters 06 and 07 indexed *what accounts declared* (their delegation
certificates). But an account's **reward balance** is ledger state - the node
computes it - so it needs local-state-query. And unlike every query so far, this
one takes an input: which credentials to report on.

## The first query with a payload

`GetFilteredDelegationsAndRewardAccounts` takes a set of stake credentials and
returns two maps: each credential's delegated pool and its reward balance. The
argument is a list of `[keyType, hash]` credentials (key type 0 = key hash):

```
  MsgQuery = [3, [0, [0, [6, [10, [[0, <cred>], ...]]]]]]
                               |    |
                               |    +-- the argument: credentials to look up
                               +-- GetFilteredDelegationsAndRewardAccounts

  result   = [[ {(0, cred): pool}, {(0, cred): reward_lovelace} ]]
```

We confirmed the wire shape against the live node: querying a pool owner's
credential returned its pool (`pool1dzr...`) and a real reward balance
(602474899 lovelace). The result's maps are keyed by a `(keyType, credential)`
pair, which is how we pull the credential back out.

## Stake addresses to credentials

A user searches a stake address like `stake_test1...`. Decoding it (chapter 25)
gives a 1-byte header plus the 28-byte credential; we drop the header to get the
credential our certificate tables and the query use. So searching a stake address
in the explorer lands on the right account.

## Persisting the snapshot

As with live stake (chapter 24), we do not query the node per web request. The
live runner's snapshot loop now also, for every credential we have seen in a
registration (`registered_stake_credentials`), asks the node for its delegation
and reward and stores them in an `account_stat` table (migration 7). The API
serves account pages from that snapshot, merged with on-chain facts:

- `registered` - from the chain (our certificate tables);
- `delegated_to` - the snapshot's pool, falling back to the on-chain delegation;
- `reward` - the snapshot's reward balance.

## The account page

The API's `/accounts/{stake}` accepts a `stake_test1...` address (or a raw
credential), and the explorer routes a `stake...` search to an account page
showing registration, delegated pool (linked), and rewards in ada.

> **Controlled stake, deferred.** cardanoscan also shows an account's total
> controlled stake (the ada in every payment address that shares this stake
> credential). That needs indexing the stake part of each payment address, which
> we do not yet do; it is a clean follow-up.

## Test first (red), make it pass (green)

Tests cover the query builder and result parser (including a credential that has a
reward but no delegation), the store's `record_account_states` / `account_state` /
`registered_stake_credentials`, the API account endpoint (rewards plus the
fall-back to on-chain delegation), and decoding a `stake_test1...` address to its
credential. A live integration test reads a real reward balance from the node.
`make check` stays green and fully covered.

## What we built

- `AccountState` and the argument-carrying `delegations_and_rewards_query` /
  `parse_delegations_and_rewards`.
- `LocalStateClient.account_states`; the snapshot loop persisting account state.
- Migration 7 (`account_stat`) and `store.record_account_states` /
  `account_state` / `registered_stake_credentials`.
- An enriched `/accounts/{stake}` and an explorer account page.

## Glossary

- **Reward balance**: the withdrawable rewards accrued to a stake account; ledger
  state, from local-state-query.
- **Stake credential**: the 28-byte hash identifying a stake account (the stake
  address is a header byte plus this).
- **Argument-carrying query**: an LSQ query that sends data (here, the credentials
  to look up) rather than just a tag.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch26): stake-account pages with delegation and rewards"
git tag ch26
```

## Next up

Further cardanoscan parity: controlled stake on accounts, an analytics/charts page
(transaction volume over time), asset/token pages, and richer transaction pages
(certificates, fees, governance on each tx).
