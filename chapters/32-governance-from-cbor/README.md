# Chapter 32 - Governance from CBOR

> **Goal:** decode governance from real blocks. The node path (chapter 10) decoded
> value and certificates but not governance proposals or votes, so the governance
> section only ever populated from synthetic tests. This chapter closes that gap so
> a real on-chain proposal and its votes show up.

When we minted and voted on a local cluster to get real data, nothing appeared in
the governance section - because the CBOR block decoder never read the two Conway
transaction-body fields that carry governance:

- **key 20, proposal procedures**: a set of `(deposit, reward_account, gov_action,
  anchor)`. The `gov_action` is a small tagged value (`(6,)` is an info action). A
  proposal has no id of its own; its id is `txid#index`, which is exactly how votes
  refer back to it.
- **key 19, voting procedures**: a map `{voter -> {gov_action_id -> [vote, anchor]}}`.
  The voter is `(role, credential)` (role 2/3 = DRep, 4 = SPO, 0/1 = committee), the
  gov action id is `(txid, index)`, and the vote is `0 = No`, `1 = Yes`, `2 =
  Abstain`.

Both shapes were read straight off the real transactions we submitted, then turned
into the `GovActionProposal` and `GovVote` values the governance indexer already
consumes. The `txid#index` id is built the same way on both sides - a proposal
from this transaction's id, a vote from the referenced id - so a vote's tally
lines up with its action.

## Test first (red), make it pass (green)

Tests decode an info-action proposal (id `txid#0`, type `InfoAction`, deposit) and
a set of votes (a DRep Yes and an SPO No, referring to the same action id), matching
the real CBOR structures. `make check` stays green and fully covered.

## What we built

- `_decode_proposals` and `_decode_votes` in the CBOR block decoder, wired into
  `_decode_tx`, so the node path now indexes governance like the model always
  supported.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch32): decode governance proposals and votes from CBOR"
git tag ch32
```

## Next up

Tabbed transaction and governance pages (summary / UTXOs / certificates /
governance), and more ledger-state views (protocol parameters, ADA pots).
