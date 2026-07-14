# Chapter 44 - Protocol updates

> **Goal:** a Protocol updates view. In Conway there is no separate protocol-update
> transaction field as in earlier eras; protocol changes are governance actions.
> This chapter surfaces the two kinds that change the protocol.

Before Conway, a transaction could carry a protocol-parameter update directly. In
Conway that mechanism is gone: parameters change through a **ParameterChange**
governance action, and the era advances through a **HardForkInitiation** action,
both ratified by votes. So "protocol updates" is a filtered view of the governance
actions we already index (chapter 32).

## A filtered view

`store.protocol_updates` returns the governance action summaries whose type is
`ParameterChange` or `HardForkInitiation`, with their tallies - reusing
`governance_action_summaries`, so no new query shape. `/governance/protocol-updates`
serves them, and the explorer adds a **Protocol updates** page (linked from the
governance section) listing each action, its type, and its tally, with a note
explaining the Conway model.

On our cluster there are no such actions yet, so the page shows an empty state; it
populates the moment a parameter-change or hard-fork action is proposed.

## Test first (red), make it pass (green)

An API test proposes a parameter change, a hard-fork initiation, and an info
action, then checks that protocol-updates returns only the first two while the full
governance list still has all three. `make check` stays green and fully covered.

## What we built

- `store.protocol_updates`; `/governance/protocol-updates`; a Protocol updates page
  in the explorer.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch44): protocol updates view (parameter change and hard fork actions)"
git tag ch44
```

## Next up

The local-tx-submission mini-protocol: submitting a transaction to the node
ourselves, over our own protocol, instead of shelling out to the cli - completing
the node-to-client set.
