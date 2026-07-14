# Chapter 79 - `chainidx run --config`

> **Goal:** a friendly way to start the whole indexer from a config file, without
> remembering an environment variable.

## Why

`python -m chainidx.live` reads its config from the `CHAINIDX_CONFIG` environment
variable. That is fine for a service manager, but on the command line
`CHAINIDX_CONFIG=config.json python -m chainidx.live` is a mouthful and easy to get
wrong. A `--config` flag is what people expect.

## What it does

```bash
chainidx run --config config.json
```

Starts everything - the follower, the explorer at `/`, the live view at `/live`, and
any configured sinks - exactly as `python -m chainidx.live` does. With no flag it
still falls back to `CHAINIDX_CONFIG`, so existing setups keep working. It is a thin
wrapper: `config.load(path)` then the same `_run_live(cfg)` the module entry point
uses.

## What we built

- A `chainidx run --config <file>` command (falls back to `CHAINIDX_CONFIG`).

## Commit and tag

```bash
git add -A
git commit -m "feat(ch79): a chainidx run --config flag to start the server"
git tag ch79
```
