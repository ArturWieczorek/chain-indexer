# Chapter 34 - Certificates browser

> **Goal:** decode every Conway certificate kind and add a Certificates section
> that browses them by category - the way a professional explorer lists pool
> registrations, delegations, DRep actions, and committee changes side by side.

Until now the CBOR decoder read only four certificate tags (pool registration,
stake registration, stake-and-vote delegation, DRep registration) and dropped the
rest. That was enough to feed the pool, account, and DRep pages, but it meant most
of the certificates a real chain carries were invisible. This chapter decodes the
whole Conway certificate set and surfaces it.

## The Conway certificate set

A certificate is a CBOR array whose first element is a tag. The Conway tags we now
decode:

| tag | certificate | category |
| --- | --- | --- |
| 0, 7 | stake registration (legacy / with deposit) | Stake Key Registration |
| 1, 8 | stake deregistration | Stake Key Deregistration |
| 2, 10, 11, 13 | delegation to a pool | Delegation |
| 9, 12 | vote delegation to a DRep | Vote Delegation |
| 3 | pool registration | Pool Registration |
| 4 | pool retirement | Pool Deregistration |
| 14 | committee hot key authorization | Committee Hot Key Authorization |
| 15 | committee cold key resignation | Committee Cold Key Resignation |
| 16 | DRep registration | DRep Registration |
| 17 | DRep deregistration | DRep Deregistration |
| 18 | DRep update | DRep Update |

A few tags register and delegate in one step (11, 13); we index them by their
delegation, which is the part later pages care about. A vote delegation's target
is a `drep`: a key or script credential, or the special `AlwaysAbstain` /
`AlwaysNoConfidence` roles, decoded by `_decode_drep`. Unknown tags are skipped
rather than guessed at.

Four new model records join the certificate union: `VoteDelegation`, `DRepUpdate`,
`CommitteeAuthHot`, and `CommitteeResignCold`.

## Storing every certificate in one place

The typed tables (pool, delegation, DRep, ...) still back the pool/account/DRep
pages. On top of them, a flat `certificate` table (migration 9) records every
certificate with a human category label, a subject id, and a detail field. It is
block-keyed, so it rolls back with everything else. `certificate_fields` maps each
certificate record to `(category, subject, detail)`, and the `CertIndexer` writes
that row for every certificate while still filling the typed tables for the kinds
that need them.

## API and explorer

- `/certificates` lists certificates newest first, optionally filtered by
  `?cert_type=`.
- `/certificates/summary` gives the per-category counts.
- The explorer gains a **Certificates** section: category chips (with counts) that
  filter the list, and a table whose subject links to the right page (pool,
  account, or DRep) and whose transaction column links to the tx.

The home page's transaction count is now a link too: it opens the block, whose page
already lists each transaction, each of which links to its detail.

## Test first (red), make it pass (green)

Decoder tests build one certificate of every tag (including the abstain and
no-confidence vote targets and an unknown tag) and assert the decoded kinds. An API
test applies a block carrying one certificate of each of the eleven categories and
checks the summary counts, the full list, category filtering, and the detail field.
`make check` stays green and fully covered.

## What we built

- Full Conway certificate decoding; `VoteDelegation`, `DRepUpdate`,
  `CommitteeAuthHot`, `CommitteeResignCold` models; `certificate_fields`.
- Migration 9 `certificate` table (rolls back with blocks); `store.certificates`
  and `store.certificate_summary`.
- `/certificates` and `/certificates/summary`; a Certificates section with
  category filters and linked subjects.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch34): decode every Conway certificate and add a Certificates browser"
git tag ch34
```

## Next up

A transaction detail with Summary / UTXOs / Metadata tabs, and governance
sub-pages (committee, protocol parameters, ADA pots) backed by new local-state
queries.
