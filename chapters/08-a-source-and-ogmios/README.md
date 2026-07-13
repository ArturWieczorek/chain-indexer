# Chapter 08 - A source and the Ogmios client

> **Goal:** stop hand-feeding synthetic blocks. Define a `ChainSource` interface
> that yields `RollForward` and `RollBackward` events, and implement it over
> Ogmios so real Conway blocks flow into our model. First real data, end to end.

Phase 1 built a complete indexer and tested it on made-up blocks. That was the
right way to get the logic correct. Now we plug in a real chain. The trick to
doing this cleanly is to define the *seam* first - an interface for "the thing
that gives me chain events" - and only then implement it.

## The two events, and the interface

A follower receives a stream of just two kinds of event, which are exactly the
chain-sync protocol's two messages:

```
  RollForward(block)     "here is the next block, apply it"
  RollBackward(point)    "back up to this point, later blocks are gone"
```

We model them as two tiny dataclasses and hide their producer behind a
`ChainSource`:

```python
class ChainSource(Protocol):
    async def find_intersection(self, points) -> Point | Origin | None: ...
    async def next_event(self) -> ChainEvent: ...
    async def close(self) -> None: ...
```

Note the `async`. Talking to a network means waiting for bytes, and
`async`/`await` lets us wait without freezing the program. If you have not met it
before: an `async def` function returns a coroutine, and `await` runs it and
waits for the result. That is all we need here.

> **Representing "before the beginning".** Chain-sync can roll us back past the
> first block, to the *origin*. We could reuse `None` for that, but `None`
> already means "no intersection found". So we add a small `Origin` marker value.
> Being able to say "before block one" precisely is worth one extra type.

## Two implementations, later

We will implement `ChainSource` twice:

- **now, over Ogmios** (this chapter) - fast to get working;
- **later, by hand** (chapter 12) - the from-scratch wire protocol.

Because both satisfy the same interface, the sync loop we write in chapter 09
never learns which one it is driving. That is the payoff of defining the seam.

There is also a `FakeSource`: a scripted, in-memory source that yields a list of
events you give it. It needs no network, so the sync loop's tests use it.

## What is Ogmios?

[Ogmios](https://ogmios.dev) is a small bridge: it connects to a cardano-node,
speaks the node's binary mini-protocols, and re-exposes them as a friendly
JSON-RPC WebSocket API. We send `findIntersection` and `nextBlock` requests and
get JSON back. It is the quickest path to real data, and it lets us validate the
whole storage and reorg design against a live chain before we take on the wire
protocol ourselves.

```
  cardano-node  <--(binary mini-protocols)-->  Ogmios  <--(JSON/WebSocket)-->  us
```

## Parse in a pure module

The WebSocket plumbing and the JSON-to-model translation are kept in separate
files on purpose:

- `ogmios_parse.py` - **pure functions**: given the JSON of a block, an output, or
  a chain-sync reply, return a `Block`, `TxOut`, or `ChainEvent`. No I/O.
- `ogmios.py` - the `OgmiosSource`: opens the WebSocket, sends requests, and hands
  the JSON to the parser.

Why split them? Because the pure parser can be tested exhaustively against
**saved, real Ogmios responses** with no server running, while the thin plumbing
is the only part that needs a live Ogmios. The fixtures under `tests/fixtures/`
were captured from Ogmios v6 talking to a real node - the JSON shapes are
observed, not guessed. That is why the parser stays inside the 100 percent
coverage gate while `ogmios.py` is excluded from it (see `pyproject.toml`).

A taste of the shapes the parser handles, straight from the chain:

```
  block:  {"id", "ancestor", "height", "slot", "transactions": [...]}
  value:  {"ada": {"lovelace": N}, "<policy>": {"<asset>": N}}
  input:  {"transaction": {"id": ...}, "index": N}
  cert:   {"type": "stakePoolRegistration", "stakePool": {"id", "pledge", "margin", ...}}
```

The pool `margin` arrives as a string fraction like `"7/20"`, so the parser turns
it into `0.35`. Small details like that are exactly why capturing real responses
beats guessing.

> **Coverage of the Ogmios path.** The staking and DRep registration and
> delegation certificates that a running cluster produces are mapped here.
> Deregistration and retirement certificates are handled by the from-scratch
> node path in chapter 12, which decodes the full transaction body; Ogmios is our
> bootstrap, not the last word.

## The integration test that proves it

`tests/test_ogmios_integration.py` is marked `integration` and skips itself when
no Ogmios is reachable, so CI stays offline. Run against a live cluster it does
the real thing: intersect at the origin, receive the roll-back to origin, then
roll forward through real Conway blocks and check their hashes are 64 hex
characters. When it passes, the whole pipeline - node, Ogmios, parser, model - is
proven against real data.

## Test first (red), make it pass (green)

The unit tests cover the `FakeSource` (scripted events, intersection, and running
out), and the parser against the saved fixtures (a real block, each certificate
kind, values with and without native assets, and both chain-sync directions).
`make check` stays green and fully covered.

## What we built

- `RollForward` / `RollBackward` events and the `ChainSource` interface.
- `Origin`, a precise marker for the pre-genesis position.
- `FakeSource` for offline tests.
- A pure Ogmios parser (`ogmios_parse.py`) and the `OgmiosSource` client.
- An integration test that follows a real chain.

## Glossary

- **Ogmios**: a bridge exposing a node's mini-protocols as a JSON WebSocket API.
- **chain-sync**: the mini-protocol for following a chain; its two messages are
  roll-forward and roll-backward.
- **`async` / `await`**: Python syntax for waiting on I/O without blocking.
- **Origin**: the position before the first block.
- **Intersection**: the newest point the follower and the source agree on; where
  to resume from.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch08): add the ChainSource interface and Ogmios client"
git tag ch08
```

## Next up

[Chapter 09 - The sync loop](../09-the-sync-loop/): we connect a source to the
store. The follower finds an intersection to resume from, then loops: roll forward
means index a block, roll backward means run the reorg engine. This is the beating
heart that ties every previous chapter together.
