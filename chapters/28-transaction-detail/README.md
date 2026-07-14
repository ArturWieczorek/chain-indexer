# Chapter 28 - Transaction detail

> **Goal:** show what a transaction *did*, not just what value it moved - its
> certificates and governance actions/votes - on the transaction page.

Transaction pages so far listed inputs and outputs. But a Cardano transaction can
also register a stake key, delegate to a pool, register a DRep, propose a
governance action, or cast votes. We already index all of that (chapters 06, 07);
this chapter surfaces it per transaction.

## One method over the activity tables

`store.tx_activity(tx_hash)` looks up the transaction, then reads every table that
records something a transaction can do, filtered to that transaction's id, and
returns short human-readable descriptions grouped into certificates, governance
proposals, and votes:

```
  delegation: <credential> -> <pool>
  pool registration: <pool>
  DRep registration: <drep>
  InfoAction: <gov_action_id>          (a proposal)
  DRep voted Yes on <gov_action_id>    (a vote)
```

Because every one of those rows carries the `tx_id`, gathering a transaction's
activity is just one filtered query per table. An unknown transaction returns
empty lists.

## API and explorer

`/txs/{hash}` now includes `certificates`, `proposals`, and `votes` alongside the
inputs and outputs, and the explorer's transaction page renders each non-empty
group as its own section. A plain value-transfer transaction shows nothing extra;
a genesis or governance transaction shows the full list of what it declared.

## Test first (red), make it pass (green)

Tests cover `store.tx_activity` on a transaction carrying stake, delegation, and
DRep certificates plus a proposal and a vote (and the empty result for an unknown
transaction), and the API including these on the transaction endpoint. `make
check` stays green and fully covered.

## What we built

- `TxActivity` and `store.tx_activity`.
- `certificates` / `proposals` / `votes` on `/txs/{hash}` and the transaction page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch28): show certificates and governance on transaction pages"
git tag ch28
```

## Next up

[Chapter 29 - Controlled stake](../29-controlled-stake/): index the stake part of
each output address so an account page can show the total ada it controls, not
just its rewards.
