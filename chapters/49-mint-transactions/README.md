# Chapter 49 - Mint transactions

> **Goal:** a Mint Transactions view under Tokens - the transactions that minted
> or burned native assets - by decoding the one transaction-body field we had not
> touched: the mint field.

We index the assets an output *holds* (chapter 04), but not the act of *minting*
them. A transaction mints (or burns) in its body's **mint** field (key 9), a map
``{policy_id: {asset_name: quantity}}`` where a positive quantity mints and a
negative one burns.

## Decode and index

`_decode_mint` reads key 9 into `Asset`s on `Tx.mint` (quantity may be negative).
A `MintIndexer` writes each into a block-keyed `mint_event` table (migration 16),
so mints roll back with their block. `store.recent_mints` returns them newest
first as `MintRecord`s.

## API and explorer

- `/assets/mints` lists recent mint and burn events (with the decoded asset name).
- The Tokens section gains sub-tabs: **Tokens** (the existing asset list) and
  **Mint Transactions**, a table of each event - asset, policy, quantity (`+` mint
  or `-` burn), and the transaction.

## Test first (red), make it pass (green)

A decoder test reads a mint and a burn from a mint field. An API test applies a
transaction that mints one asset and burns another and checks both events come
back against that transaction. `make check` stays green and fully covered.

## What we built

- `Tx.mint` and `_decode_mint`; `MintRecord`; migration 16 `mint_event`;
  `MintIndexer`; `store.recent_mints`.
- `/assets/mints` and a Mint Transactions sub-tab in the Tokens section.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch49): mint transactions view from the mint field"
git tag ch49
```

## Next up

Fetching off-chain metadata (pool name/ticker, asset images) behind configuration,
and UI polish (favicons, theme and colour selection).
