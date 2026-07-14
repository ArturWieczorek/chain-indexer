# Chapter 68 - Richer events and a filter

> **Goal:** make the event stream rich enough to filter, adder-style - so the next
> chapter can push exactly the events a consumer asked for to a webhook.

## The idea

[adder](https://github.com/blinklabs-io/adder) is an event pipeline: tail the chain,
**filter** events (by address, asset, policy, type), and push the survivors to an
output. We already have the tail (the follower) and the bus (chapter 16). Two things
were missing: events carrying enough detail to filter on, and the filter itself.

## Richer events

`describe_block` emitted a block event and cert/governance events, but nothing that
said "this transaction paid this address" or "this transaction touched this policy".
So it now also emits one **`transaction`** event per transaction, carrying:

- `addresses` - every output address;
- `policies` and `assets` - the policies and `policyid.assetname` pairs touched by
  the outputs **and** the mint (so minting is visible);
- `tx_hash`, `block_no`, `lovelace` (total out), `output_count`, `mint_count`.

The rollback event was already published by the follower (`{"type": "rollback",
...}`), so a filter that wants reorgs gets them for free.

## The filter

`patterns.EventFilter` is a pure value with four optional fields: `types`,
`addresses`, `policies`, `assets`. Its semantics are adder's:

- **OR within a field** - any of the listed addresses counts as a match;
- **AND across fields** - an address you want *and* a policy you want;
- an empty field does not constrain, so the empty filter matches everything;
- an event that does not carry a field the filter constrains on cannot match it -
  so filtering by address selects only the address-bearing (`transaction`) events.

`matches(event)` is one expression over the four fields, so it is trivial to test
every combination.

## Test first (red), make it pass (green)

`test_event.py` checks the new `transaction` event gathers addresses, policies, and
assets (from outputs and mint). `test_patterns.py` pins the filter's OR-within,
AND-across, empty-matches-all, by-type, and missing-field behaviour. `make check`
stays green at 100 percent.

## What we built

- `event._transaction_event` and a `transaction` event in `describe_block`.
- `patterns.EventFilter` (pure), the adder-style matcher.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch68): richer per-transaction events and an adder-style filter"
git tag ch68
```

## Next

The webhook sink: subscribe to the bus, apply an `EventFilter`, and POST the
survivors (including rollbacks) to configured URLs.
