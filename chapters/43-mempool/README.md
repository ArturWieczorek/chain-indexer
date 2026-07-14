# Chapter 43 - The mempool (local-tx-monitor)

> **Goal:** a mempool view - the pending transactions a node holds before they
> reach a block - built on the fifth and final node-to-client mini-protocol,
> local-tx-monitor. With it, we speak the whole node-to-client suite by hand.

## The fifth mini-protocol

We already hand-wrote handshake (chapter 11), chain-sync (chapter 12), and
local-state-query (chapter 20). Local-tx-monitor (mini-protocol id 9) is the last:
it exposes the node's mempool. As with the others, the wire shapes were confirmed
against a live node before this code was written:

- `MsgAcquire  = [1]`   -> `MsgAcquired = [2, slot]`
- `MsgGetSizes = [9]`   -> `[10, [capacity, size, numberOfTxs]]`
- `MsgNextTx   = [5]`   -> `[6]` (no more) or `[6, [era, CBORTag(24, tx)]]`
- `MsgRelease  = [3]`, `MsgDone = [0]`

A mempool transaction arrives as raw CBOR wrapped in tag 24. Its id is the
blake2b-256 of the transaction body's exact bytes - the same rule as block
transactions (chapter 10) - so `cbor_blocks.tx_id_of_bytes` reads the body's byte
span and hashes it rather than re-encoding.

## Modules (codec vs socket)

Mirroring local-state-query, the logic splits in two:

- `txmonitor.py` (pure, fully tested): the messages and the reply parsers
  (`parse_acquired`, `parse_sizes`, `parse_next_tx`).
- `mempoolclient.py` (integration, coverage-omitted): `MempoolClient` opens the
  socket, handshakes, acquires a snapshot, reads the sizes and the pending
  transaction ids, and releases - returning a `MempoolStatus`.

## Serving it

The mempool is live state, not indexed data, so it cannot be served from the
store; it is queried on demand. `create_app` takes an optional `mempool_source`
callable, and `/mempool` calls it - returning `{"available": false}` when no node
connection is wired in (as in unit tests). The live runner passes the real
`MempoolClient`. The explorer adds a **Mempool** section: capacity and fill, the
pending count, and each pending transaction id (linking to its page, where it
resolves once mined).

## Test first (red), make it pass (green)

`tx_id_of_bytes` is checked against a real transaction we captured from a live
mempool (its id is asserted exactly). The codec tests cover the builders, the
acquired/sizes/next-tx parsers (including the empty case and error branches), and
computing an id from a wrapped transaction. The API test covers `/mempool` both
unavailable and with a source. `make check` stays green and fully covered.

## What we built

- `cbor_blocks.tx_id_of_bytes`; `txmonitor` codec; `MempoolStatus` model;
  `MempoolClient`; mini-protocol id 9 in the mux.
- `create_app` mempool injection and `/mempool`; a Mempool section in the explorer.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch43): mempool view over the local-tx-monitor mini-protocol"
git tag ch43
```

## Where this leaves the project

All five node-to-client mini-protocols are now hand-written: handshake,
chain-sync, local-state-query, and local-tx-monitor (local-tx-submission aside, as
we submit with the cli). The explorer covers the cardanoscan-shaped surface -
blocks, transactions, mempool, epochs, pools, governance (committee, protocol
parameters, DReps, actions), certificates, withdrawals, tokens and policies, top
holders, and analytics - over an indexer fed entirely by from-scratch protocols.
