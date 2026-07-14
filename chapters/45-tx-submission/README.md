# Chapter 45 - Submitting transactions (local-tx-submission)

> **Goal:** submit a signed transaction to the node ourselves, over the
> local-tx-submission mini-protocol - the last node-to-client protocol we did not
> speak. With it, all five are hand-written.

Until now we handed transactions to the node with `cardano-cli transaction submit`.
This chapter replaces that with our own client speaking mini-protocol id 6.

## The protocol

Local-tx-submission is a one-shot exchange, confirmed against a live node before
this code was written:

- `MsgSubmitTx = [0, [era, CBORTag(24, txBytes)]]`  (client submits)
- `MsgAcceptTx = [1]`                                (node accepted)
- `MsgRejectTx = [2, reason]`                        (node rejected)
- `MsgDone     = [3]`

A submitted transaction is the raw signed CBOR, era-wrapped and tagged 24 - the
same envelope local-tx-monitor hands back (chapter 43). The rejection reason is a
nested ledger-error structure; we pull the readable text out of it (for example
"All inputs are spent...").

## Modules (codec vs socket) and the cli

As with the other mini-protocols, the logic splits in two:

- `txsubmit.py` (pure, fully tested): `submit_message`, `done_message`, and
  `parse_reply` returning a `SubmitResult` (accepted, or a readable reason).
- `txsubmitclient.py` (integration, coverage-omitted): `TxSubmitClient` opens the
  socket, handshakes, submits, and reads the reply.

`chainidx submit <tx-file>` reads a signed transaction (a cardano-cli envelope's
`cborHex`, or a raw `.cbor` file) and submits it, printing `accepted` or the
rejection reason. Verified live: submitting a transaction returns `accepted` and it
lands on-chain; resubmitting the same one returns `rejected: All inputs are
spent...`.

## Test first (red), make it pass (green)

Codec tests cover the submit envelope (era-wrapped, tag 24), the accept reply, and
the reject reply - including extracting the readable reason from the real nested
structure a node returned, and the repr fallback. `make check` stays green and
fully covered.

## What we built

- `SubmitResult` model; `txsubmit` codec; `TxSubmitClient`; mini-protocol id 6 in
  the mux; a `chainidx submit` command.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch45): submit transactions over the local-tx-submission mini-protocol"
git tag ch45
```

## Where this leaves the project

All five node-to-client mini-protocols are now hand-written: handshake,
chain-sync, local-tx-submission, local-state-query, and local-tx-monitor. The
project follows a chain, indexes it reorg-aware, reads ledger state, watches the
mempool, and submits transactions - all over protocols implemented from the bytes
up, with a cardanoscan-shaped explorer on top.
