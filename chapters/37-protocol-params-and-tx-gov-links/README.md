# Chapter 37 - Protocol parameters and transaction governance links

> **Goal:** surface the current protocol parameters as a page (the first ledger
> state we persist for the explorer), and make a transaction's governance actions
> and votes link to the action they refer to instead of showing as text.

## Protocol parameters

The local-state-query client already reads the current protocol parameters
(chapter 20) - they rode along in the `LedgerSnapshot` and only `n_opt` was kept,
for pool saturation. This chapter persists all of them.

Migration 11 adds a `protocol_param` table, a small key/value store like
`ledger_stat`. It is ledger state, not chain data, so it is not block-keyed and
does not roll back: the next snapshot simply replaces it. `record_protocol_params`
replaces the row set, `protocol_params` reads it back, and the live snapshot loop
records them each cycle alongside the stake distribution. `/protocol-parameters`
serves the map, and the explorer adds a **Protocol parameters** page (linked from
the governance section) that labels each parameter and shows deposits and costs in
ada.

## Governance links on the transaction page

The transaction page listed proposals and votes as pre-formatted strings, so a
governance action a transaction proposed or voted on could not be clicked. Two new
queries return them as typed records instead:

- `proposals_for_tx` returns the `GovActionProposal`s a transaction created.
- `votes_for_tx` returns its votes; `GovVoteRecord` gains a `gov_action_id` field
  (populated here, empty when votes are listed for an already-known action) so a
  vote can link to the action it refers to.

The transaction Summary tab now renders both as tables whose action id links to the
governance action page.

## Test first (red), make it pass (green)

An API test drives `/protocol-parameters`: empty at first, then the recorded
values, then a replacement (confirming a new snapshot overwrites the old). The
transaction test now checks the structured proposal and vote payloads (each with
its `gov_action_id`). `make check` stays green and fully covered.

## What we built

- Migration 11 `protocol_param`; `store.record_protocol_params` /
  `store.protocol_params`; the snapshot loop records them; `/protocol-parameters`
  and a Protocol parameters page.
- `store.proposals_for_tx` / `store.votes_for_tx`; `GovVoteRecord.gov_action_id`;
  structured, linked proposals and votes on the transaction page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch37): protocol parameters page and linked governance on transactions"
git tag ch37
```

## Next up

The committee view (giving committee voters a page of their own) and ADA pots,
backed by further local-state queries.
