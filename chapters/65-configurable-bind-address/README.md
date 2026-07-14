# Chapter 65 - A configurable bind address (run more than one network)

> **Goal:** stop hard-coding where the server listens, so you can run the indexer
> against several networks (preprod *and* preview) at the same time.

## The problem

The live runner bound the explorer to `127.0.0.1:8000` in the source. You could
already keep two networks' data apart by giving each its own `db_path`, but you
could not run both servers at once: the second one failed to bind, because the port
was fixed. That is a real limitation for anyone following more than one testnet.

## The fix

Two new config fields, `host` and `port` (defaulting to `127.0.0.1` and `8000`, so
nothing changes for a single run), each with a `CHAINIDX_HOST` / `CHAINIDX_PORT`
environment override like every other setting. The live runner passes them to
uvicorn instead of the literals, and prints the address it actually bound.

Now one config file per network, each with its own database and port, runs side by
side:

```jsonc
// preprod.json
{ "network_magic": 1, "db_path": "preprod.db", "port": 8000, ... }
// preview.json
{ "network_magic": 2, "db_path": "preview.db", "port": 8001, ... }
```

```bash
CHAINIDX_CONFIG=preprod.json python -m chainidx.live   # http://127.0.0.1:8000
CHAINIDX_CONFIG=preview.json python -m chainidx.live   # http://127.0.0.1:8001
```

Setting `host` to `0.0.0.0` also lets the explorer be reached from another machine
(bind it only on a trusted network - there is no authentication).

## Test first (red), make it pass (green)

`test_config.py` gains the defaults, the file values, and the env-wins-over-file
behaviour for `host`/`port`. The `live.py` wiring is in the coverage-omitted runner,
like the rest of the server bootstrap. `make check` stays green at 100 percent.

## What we built

- `Config.host` / `Config.port` (+ `CHAINIDX_HOST` / `CHAINIDX_PORT`).
- The live runner binds and reports the configured address.
- A "run more than one network" section in the project README.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch65): a configurable bind address so multiple networks run at once"
git tag ch65
```
