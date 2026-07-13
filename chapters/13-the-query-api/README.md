# Chapter 13 - The query API

> **Goal:** expose the indexed data over HTTP. A small, Blockfrost-shaped REST API
> that serves blocks, transactions, addresses, assets, pools, and governance -
> the read side that the CLI and the explorer will both build on.

We have spent twelve chapters filling a database. Now we let the world read it.
Phase 1 was systems; this is where the full-stack layer begins, and it is
deliberately thin: the API translates store queries into JSON and does nothing
else.

## Blockfrost-shaped endpoints

[Blockfrost](https://blockfrost.io) is the Cardano data API most developers know,
so we borrow its endpoint shapes. Anyone who has used it will find ours familiar:

| Endpoint | Returns |
| -------- | ------- |
| `GET /health` | status and current tip height |
| `GET /blocks/latest` | the tip block |
| `GET /blocks?limit=N` | the most recent blocks |
| `GET /blocks/{hash}` | one block (with its transaction hashes) |
| `GET /txs/{hash}` | a transaction's inputs and outputs |
| `GET /addresses/{addr}` | an address's balance and unspent outputs |
| `GET /assets` | native assets currently held |
| `GET /pools` | active stake pools |
| `GET /accounts/{stake}` | a stake account's registration and delegation |
| `GET /governance/actions` | proposed actions with vote tallies |

## A factory, not a global

We build the app with a function that takes a store:

```python
def create_app(store: Store) -> FastAPI:
    app = FastAPI(...)
    @app.get("/health")
    def health():
        tip = store.tip()
        return {"status": "ok", "tip_height": tip.block_no if tip else None}
    ...
    return app
```

Why a factory? Because it makes the API trivially testable. A test hands
`create_app` a store full of synthetic data and drives it with a `TestClient` -
no server, no network, no database file. `create_default_app` (used by `make api`)
is the one place that opens a real database, and it is excluded from the coverage
gate because it needs one.

> **FastAPI in one breath.** `@app.get("/path")` registers a function as the
> handler for that URL. Whatever the function returns is serialized to JSON.
> Raising `HTTPException(status_code=404, ...)` sends an error response. That is
> all we use.

## Route order matters

`GET /blocks/latest` is declared *before* `GET /blocks/{block_hash}`. FastAPI
matches routes in order, so if the parameterized route came first, a request for
`/blocks/latest` would be read as "the block whose hash is `latest`". Ordering the
specific route ahead of the general one avoids that. It is a small thing that
bites everyone once.

## One thread-safety note

SQLite connections are tied to the thread that created them, but FastAPI serves
sync handlers from a threadpool. So the store opens its connection with
`check_same_thread=False`. That is safe here because the follower is the only
writer and the API only reads; a higher-traffic service would use a connection
per request instead. Chapter 18 revisits this.

## Proven on real data

Run against a store that just followed a real cardonnay cluster, the API answers
truthfully: `/health` reports the real tip height, `/blocks/latest` returns the
real tip hash, and `/pools` lists the cluster's three real pool ids. The read side
works end to end.

## Test first (red), make it pass (green)

The tests populate a store with two blocks (funding, a spend, a pool, a stake
registration, a DRep, a governance vote) and check each endpoint, including the
404s for a missing block, a missing transaction, and an empty store. `make check`
stays green and fully covered.

## What we built

- `chainidx.api.create_app`: a Blockfrost-shaped REST API over the store.
- Small serializers turning our dataclasses into JSON.
- Full test coverage via a `TestClient` and synthetic data.

## Glossary

- **REST API**: an HTTP interface where URLs name resources and `GET` reads them.
- **FastAPI**: the Python web framework we use; handlers return JSON-able values.
- **Factory**: a function that builds the app, so tests can inject a store.
- **Blockfrost**: a well-known Cardano data API whose endpoint shapes we echo.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch13): add the Blockfrost-style REST query API"
git tag ch13
```

## Next up

[Chapter 14 - The CLI](../14-the-cli/): the same data from the terminal. A small
`chainidx` command to look up blocks, address balances, transactions, pools, and
governance - handy for scripting and for checking the indexer at a glance.
