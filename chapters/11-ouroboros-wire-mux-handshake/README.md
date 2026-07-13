# Chapter 11 - Ouroboros wire I: mux and handshake

> **Goal:** open the node's socket ourselves. Build the multiplexer framing that
> wraps every message, and perform the handshake that negotiates a protocol
> version. By the end we speak the first words of the node's own language, with no
> bridge in between.

This is where the project earns its headline. Ogmios was a translator; now we
talk to the node directly, in the binary protocol it actually uses. Very few
people have hand-written a blockchain's wire protocol, and it turns out to be
approachable if you take it one layer at a time. There are two layers here: the
framing (mux) and the first mini-protocol (handshake).

## The multiplexer

A cardano-node speaks several mini-protocols - handshake, chain-sync, and more -
over a *single* connection. To share one socket, every message is wrapped in an
8-byte header (a "mux SDU header") that says which mini-protocol it belongs to and
how long it is:

```
   0               4       6       8   (byte offset)
   +---------------+-------+-------+
   | transmit time | proto | len   |     all big-endian
   +---------------+-------+-------+
     uint32          uint16  uint16
```

- **transmit time**: the low 32 bits of a microsecond clock. The node uses it for
  its own accounting; what we put there does not affect correctness.
- **proto**: the mini-protocol number (handshake is 0, chain-sync is 5). Its top
  bit is the *direction*: 0 for messages from us (the initiator), 1 for messages
  from the node (the responder). When we read a header we mask that bit off.
- **len**: how many payload bytes follow.

`pack_header` and `unpack_header` are a few lines of `struct`. The only real work
is reassembly: a single mini-protocol message can be larger than one 65535-byte
frame, so `MuxConnection.receive` keeps a buffer and pulls frames until a complete
CBOR message can be decoded from it - then returns that message and keeps any
leftover bytes for next time. We test this with in-memory streams: a message in
one frame, a message split across two frames, and two messages in one frame.

> **Why CBOR marks the message boundary.** Every mini-protocol message is a single
> CBOR value, so "have I received a whole message?" is the same question as "does
> this buffer decode as one CBOR value yet?" We lean on `cbor2` to answer it,
> which keeps the mux itself tiny.

## The handshake

The first mini-protocol to run on a new connection is the handshake: the client
proposes the versions it supports, and the node accepts one or refuses. One
message each way.

```
  propose:  [0, {version: versionData}]     (us -> node)
  accept:   [1, version, versionData]       (node -> us)
  refuse:   [2, reason]                      (node -> us)
```

Two node-to-client details matter, and we confirmed both against a live node
rather than trusting documentation:

1. **Versions carry a flag.** The number on the wire is `0x8000 | version`. So we
   propose `{0x8000 | 9: ..., 0x8000 | 10: ..., ...}` and strip the flag off
   whatever the node accepts.
2. **Version data is `[networkMagic, queryFlag]`.** We send the network magic
   (42 for a cardonnay cluster) and `query = False`.

`negotiate` sends the proposal over the mux and reads the reply; `parse_reply`
returns the accepted version or raises `HandshakeError` on refusal.

## Confirmed against the real node

The unit tests drive mux and handshake over in-memory streams, so they are fast
and offline. But the payoff is the integration test: it opens the actual node
socket, runs the handshake, and checks the node accepts a version. When that
passes, our framing and our handshake bytes are exactly right - the node agreed to
talk to us. (Getting the `0x8000` version flag and the `[magic, query]` shape
right is precisely the kind of thing you cannot guess; we discovered them by
proposing to the live node and reading its reply.)

## Test first (red), make it pass (green)

Unit tests cover header packing both directions, message reassembly in three
shapes, proposing and parsing handshake messages, and a full negotiation over a
stream. `make check` stays green and fully covered; the live handshake is an
opt-in integration test.

## What we built

- `chainidx.mux`: `pack_header` / `unpack_header` and a reassembling
  `MuxConnection`.
- `chainidx.handshake`: `propose_message`, `parse_reply`, and `negotiate`.
- An integration test that handshakes with a real node.

## Glossary

- **Mini-protocol**: one of the conversations the node multiplexes over a
  connection (handshake, chain-sync, ...).
- **Mux / SDU header**: the 8-byte frame header identifying a message's protocol
  and length.
- **Initiator / responder**: the two ends; the header's top protocol bit says
  which one sent a message.
- **Handshake**: the version-negotiation mini-protocol that runs first.
- **Network magic**: a number identifying which network you are on (42 here).

## Commit and tag

```bash
git add -A
git commit -m "feat(ch11): hand-write the mux framing and handshake"
git tag ch11
```

## Next up

[Chapter 12 - Ouroboros wire II](../12-ouroboros-wire-chain-sync/): the chain-sync
mini-protocol. We find an intersection, request blocks, and receive roll-forward
and roll-backward messages - assembling a `NodeSource` that satisfies the same
`ChainSource` interface as Ogmios. Then we point the follower at it and delete
Ogmios from the pipeline.
