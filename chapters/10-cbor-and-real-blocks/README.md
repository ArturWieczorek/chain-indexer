# Chapter 10 - CBOR and real blocks

> **Goal:** decode a real Cardano block from its raw bytes. Learn what CBOR is,
> unwrap the block structure, and - the part that trips everyone up - compute the
> block hash and transaction ids correctly, from the original bytes.

Ogmios handed us tidy JSON. The node itself does not: over its socket it sends
blocks as **CBOR**. To drop Ogmios (chapters 11 and 12) we must decode CBOR
ourselves. This chapter builds that decoder and proves it against real blocks
captured from a live node - the expected hashes in the tests are the actual
on-chain hashes.

## What is CBOR?

CBOR (Concise Binary Object Representation, RFC 8949) is a binary format with the
same data model as JSON - numbers, strings, arrays, maps - but encoded as compact
bytes instead of text. Where JSON writes the three characters `[1]`, CBOR writes
two bytes. Cardano uses it because blocks are large and must be hashed
deterministically, and a binary format is smaller and more precise than text.

We use the `cbor2` library to turn bytes into Python values, the same way `json`
turns text into dicts and lists. `cbor2.loads(data)` gives back ints, bytes,
lists, and dicts.

## Unwrapping a block

Chain-sync (chapter 12) delivers each block as a CBOR **tag 24** value - "this is
an encoded CBOR data item" - wrapping the real block bytes:

```
  CBORTag(24, <block bytes>)
        |
        v  decode the wrapped bytes
  [ era, [ header, [tx_body, ...], [witnesses...], {aux}, [invalid] ] ]
```

We need two things from it: the **header** (for the block's identity) and the
**transaction bodies** (for their contents). The header body holds the block
number, slot, and previous-block hash; each tx body is a map keyed by integers
(`0` = inputs, `1` = outputs, `4` = certificates, and so on).

## The subtlety: hash the original bytes

Here is the trap, and it is worth slowing down for.

A block's hash is the blake2b-256 of the header's bytes. A transaction's id is the
blake2b-256 of the tx body's bytes. The obvious approach - decode the block into
Python, then re-encode a piece and hash it - **does not work**. Re-encoding can
reorder a map's keys or serialize a set differently, so the bytes differ and the
hash comes out wrong. We verified this: a re-encoded tx body hashed to something
that was not the real transaction id.

Why does it matter? Because a later transaction's input points back at an output
using the creating transaction's *real* id. If we stored a made-up id, no spend
would ever match. So we must hash the exact bytes the node sent.

To get them, we decode element by element and track byte offsets:

```python
_read_array_header(reader)          # learn how many elements follow
start = reader.tell()
header = decoder.decode()           # decode one element
header_bytes = inner[start:reader.tell()]   # the exact slice it occupied
block_hash = blake2b(header_bytes)  # hash the original bytes
```

`_read_array_header` is the only place we touch CBOR at the byte level: it reads
an array's head byte to learn the element count, leaving the reader poised at the
first element so we can measure each one. Everything else defers to `cbor2`. This
tiny bit of low-level work is what makes the hashes correct.

## Decoding the contents

With the bytes-hashing solved, the rest is straightforward mapping:

- **inputs** (`body[0]`) are `(tx_hash, index)` pairs - note the node encodes them
  as a CBOR *set*, which `cbor2` gives us as a Python set;
- **outputs** (`body[1]`) are `[address, value]`, where value is either plain
  lovelace or `[lovelace, {policy: {asset: qty}}]` for native assets;
- **certificates** (`body[4]`) are tagged arrays; we map pool registration (`3`),
  stake registration (`7`), stake delegation (`10`), and DRep registration (`16`),
  the kinds a running cluster produces. The rest follow the same shape.

Addresses and hashes are kept as hex here (real explorers bech32-encode addresses;
chapter 18 notes the difference).

## Proven against real blocks

The tests decode two blocks captured from a live node. For the block at height 33
they assert the decoder reproduces the **real** block hash
`7058a7c4...` and the **real** first transaction id `d97b618e...`, and that its
certificates include a pool registration, a stake registration, a delegation, and
a DRep registration. A second test feeds a decoded block straight into the store
and checks the pools appear. Decoding is not just plausible; it is byte-correct.

## Test first (red), make it pass (green)

Tests cover both real blocks (a full one and an empty one, which exercises the
"no previous block" path), value decoding with and without native assets, and the
array-header reader in both its short and long forms. `make check` stays green and
fully covered.

## What we built

- `chainidx.cbor_blocks.decode_block`: raw node block bytes to a `Block`.
- Correct, byte-exact block hashes and transaction ids.
- A small `_read_array_header` for offset-tracked decoding.

## Glossary

- **CBOR**: a compact binary format with JSON's data model (RFC 8949).
- **Tag 24**: a CBOR tag meaning "the following bytes are themselves CBOR".
- **blake2b-256**: the hash function Cardano uses for block and transaction ids.
- **Byte-exact hashing**: hashing the original serialized bytes, not a
  re-encoding, so the hash matches the network's.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch10): decode real Cardano blocks from CBOR"
git tag ch10
```

## Next up

[Chapter 11 - Ouroboros wire I](../11-ouroboros-wire-mux-handshake/): we open the
node's socket ourselves. We build the multiplexer framing that wraps every
message and perform the handshake that negotiates a protocol version - the first
half of speaking the node's language without any bridge.
