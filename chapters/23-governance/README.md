# Chapter 23 - Governance

> **Goal:** a Governance section in the explorer - delegated representatives
> (DReps) and governance actions with their vote tallies and individual votes -
> built on the Conway data we already index.

Chapter 07 indexed governance into tables (DReps, proposals, votes). This chapter
turns that into pages, the way cardanoscan has a Governance section. There is no
new chain data here; it is the query and presentation layer over what we already
have.

## What the section shows

- **DReps**: each active delegated representative, its registration deposit, and
  how many votes it has cast.
- **Governance actions**: each proposed action, its type (for example
  `TreasuryWithdrawals`, `InfoAction`), its deposit, and a Yes / No / Abstain
  tally.
- **Action detail**: the individual votes on an action - who voted (role and id)
  and how.

## Store methods

Three read methods aggregate the existing tables:

- `governance_action_summaries()` joins each `gov_action_proposal` with its
  `voting_procedure` tally, flattening the tally to `yes` / `no` / `abstain`
  counts (so the result is a plain, frozen record).
- `governance_action_votes(id)` returns the individual `GovVoteRecord`s.
- `drep_summaries()` returns each active DRep with its latest deposit and its
  DRep-role vote count.

The vote count uses `voter_role = 'DRep'` so an action's Yes/No tally and a DRep's
"votes cast" line up with how the ledger attributes votes.

## API and explorer

The API gains `/governance/actions` (summaries), `/governance/actions/{id}`
(summary plus the votes), `/governance/dreps`, and `/governance/dreps/{id}`. The
explorer gains a **Governance** nav entry: a page listing actions and DReps side
by side, with each action linking to a detail page that shows every vote.

On a fresh local cluster there are usually no governance *actions* submitted yet,
so that table shows an empty state - but the DReps registered at genesis appear
immediately (our cluster has five). Submit a governance action with `cardano-cli`
and it shows up here with its live tally.

## Test first (red), make it pass (green)

Tests cover the store's action summaries (type, deposit, Yes/No/Abstain tally),
the individual vote records, and the DRep summaries (deposit and votes cast), plus
all four API endpoints including the 404s. `make check` stays green and fully
covered.

## What we built

- `GovActionSummary`, `GovVoteRecord`, `DRepSummary` models.
- `store.governance_action_summaries` / `governance_action_votes` /
  `drep_summaries`.
- API governance endpoints (list + detail for actions and DReps).
- A Governance section in the explorer.

## Glossary

- **DRep**: a delegated representative that votes on behalf of ada holders who
  delegate their voting power to it.
- **Governance action**: an on-chain proposal (parameter change, treasury
  withdrawal, and so on) that is voted on.
- **Tally**: the count of Yes / No / Abstain votes on an action.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch23): add the governance explorer section"
git tag ch23
```

## Next up

[Chapter 24 - Accounts and rewards](../24-accounts/): stake-account pages -
delegation, controlled stake, and rewards - using local-state-query's account and
reward queries, and surfacing live stake on the pool pages.
