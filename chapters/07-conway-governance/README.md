# Chapter 07 - Conway governance

> **Goal:** index Cardano's newest layer - delegated representatives (DReps),
> governance action proposals, and votes - as one more indexer on the same
> pipeline. By now this should feel routine, and that is the whole point.

The Conway era added on-chain **governance**: a way for the community to change
protocol parameters, spend from the treasury, elect a constitutional committee,
and more, by proposing **governance actions** and **voting** on them. Three kinds
of actor vote: the **constitutional committee**, **DReps** (delegated
representatives that ada holders delegate their voting power to), and **stake pool
operators** (SPOs).

Like staking, all of this arrives inside transactions, so chain-sync already
carries it. And like staking, adding it is the same three-step recipe. If chapter
06 convinced you the architecture holds, this chapter is the proof that it keeps
holding as the chain grows.

## What we index

Two new certificate kinds (they are certificates, like staking ones):

| Certificate | Meaning |
| ----------- | ------- |
| `DRepRegistration` | someone registers as a DRep (with a deposit) |
| `DRepDeregistration` | a DRep retires |

And two things that are *not* certificates - they are their own fields in a
Conway transaction body:

| Field | Meaning |
| ----- | ------- |
| `GovActionProposal` | a proposed governance action (type, deposit, return address) |
| `GovVote` | a vote (`Yes` / `No` / `Abstain`) by a role (`DRep` / `SPO` / `ConstitutionalCommittee`) on an action |

Because proposals and votes are transaction-body fields rather than certificates,
they get their own indexer, `GovIndexer`, while the DRep certificates extend the
existing `CertIndexer`.

## Exhaustiveness the compiler checks

`CertIndexer` dispatches on the certificate type with `isinstance`. Adding the two
DRep kinds means the certificate union now has seven members. The dispatch handles
six with `elif` and lets the final `else` be the seventh - and here is the useful
part: because `Certificate` is a closed union, if we had forgotten one, mypy would
narrow the `else` to the leftover type and our SQL for the "last case" would not
type-check against it. The type checker keeps the dispatch honest as the union
grows. This is a real benefit of modelling the domain as typed dataclasses rather
than dictionaries.

## Three steps again

1. **Indexers.** Extend `CertIndexer` (DRep certs), add `GovIndexer` (proposals,
   votes), register it in `default_indexers()`.
2. **Tables (migration 4).** `drep_registration`, `drep_deregistration`,
   `gov_action_proposal`, `voting_procedure` - all block-keyed.
3. **Rollback.** Add the four table names to `_ROLLBACK_TABLES`. Done.

No governance-specific rollback code exists, and none is needed. The test
`test_governance_rolls_back_with_its_block` rolls back a proposal's block and
watches the proposal and its votes vanish while an earlier DRep registration
survives - all from the same generic engine written in chapter 05.

## Derived views

- `dreps()` - DReps registered and not retired.
- `governance_actions()` - the ids of proposed actions.
- `vote_tally(gov_action_id)` - a `{Yes, No, Abstain}` count for an action.

The vote tally is a plain `GROUP BY`. It is the seed of something the dashboard
will show live in chapter 16: votes landing on an action in real time, and, if a
reorg discards the block they were in, the tally rolling back in front of you.

## Test first (red), make it pass (green)

Tests cover DReps registering and retiring, an action being recorded, votes being
tallied by outcome, and everything rolling back with its block. `make check` stays
green and fully covered.

## What we built

- DRep certificate types plus `GovActionProposal` and `GovVote` on `Tx`.
- `GovIndexer`, and DRep handling in `CertIndexer`.
- Migration 4 (four governance tables), wired into the rollback loop.
- Derived views: `dreps`, `governance_actions`, `vote_tally`.

With this, **Phase 1 is complete**: a reorg-aware indexer that captures ledger
value, staking, and governance from blocks. Everything so far ran on synthetic,
in-memory blocks. The next phase connects it to a real chain.

## Glossary

- **Governance action**: an on-chain proposal to change the system (parameters,
  treasury, committee, constitution, or an informational action).
- **DRep**: a delegated representative that votes on behalf of ada holders who
  delegate their voting power to it.
- **SPO**: stake pool operator, one of the three voting roles.
- **Constitutional committee**: a body that votes on the constitutionality of
  actions.
- **Voting procedure**: a single cast vote (`Yes` / `No` / `Abstain`).

## Commit and tag

```bash
git add -A
git commit -m "feat(ch07): index Conway governance (DReps, proposals, votes)"
git tag ch07
```

## Next up

[Chapter 08 - A source and the Ogmios client](../08-a-source-and-ogmios/): we
stop hand-feeding synthetic blocks. We define a `ChainSource` interface - the
thing that yields `RollForward` and `RollBackward` events - and implement it over
Ogmios, a bridge that speaks Cardano's mini-protocols and hands us JSON. First
real data, end to end, against the running cluster.
