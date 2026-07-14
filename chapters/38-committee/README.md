# Chapter 38 - The constitutional committee

> **Goal:** a Committee view - the constitutional committee members and their
> status - built entirely from the certificates we already index, no new node
> query needed.

Conway's constitutional committee votes on governance actions. A member holds a
**cold** credential and authorizes a **hot** credential to vote on its behalf; it
can later resign its cold credential. We decoded both certificates in chapter 34
(`Committee Hot Key Authorization` and `Committee Cold Key Resignation`), so the
committee is already in the `certificate` table - this chapter just reads it back
as a view.

## Deriving the committee

`store.committee_members` treats every cold credential that authorized a hot key as
a member. Its current hot key is the most recent authorization (later ones replace
earlier ones), and it counts as resigned once a resignation certificate exists for
that cold credential. `store.committee_member` looks one up by cold credential.
Because this is derived from block-keyed certificates, it rolls back for free with
everything else - no new table, no new query.

## API and explorer

- `/governance/committee` lists the members (cold credential, current hot
  credential, resigned or active).
- `/governance/committee/{cold_credential}` returns one member, or 404.
- The explorer gains a **Committee** page (linked from the governance section) and
  a per-member page. A governance action's committee voters now link into the
  committee section instead of being dead text.

## Test first (red), make it pass (green)

An API test applies a block with two authorizations and one resignation, then
checks the list (one active, one resigned), the per-member lookup, and the 404 for
an unknown credential. `make check` stays green and fully covered.

## What we built

- `CommitteeMember` model; `store.committee_members` / `store.committee_member`.
- `/governance/committee` and `/governance/committee/{cold_credential}`.
- A Committee page and per-member page, and committee voter links on governance
  actions.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch38): constitutional committee view from certificates"
git tag ch38
```

## Next up

ADA pots (treasury, reserves, deposits) via a further local-state query, then the
remaining blockchain sections: withdrawals, protocol updates, and top
accounts/addresses.
