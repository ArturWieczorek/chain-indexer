# Security policy

chain-indexer is a teaching project. It is a read-only chain follower and query
layer: it connects to a `cardano-node` you run, indexes public chain data, and
serves it over a local HTTP API and web page. It never holds keys and never signs
anything (transaction submission takes an already-signed transaction file).

## Reporting a vulnerability

If you find a security issue, please report it privately rather than opening a
public issue. Email **artur.wieczorek@iohk.io** with:

- a description of the issue and its impact,
- steps to reproduce, and
- any relevant configuration or output.

You can expect an acknowledgement within a few days. Once a fix is available, the
issue can be disclosed publicly.

## Scope and hardening notes

- The API and explorer are **unauthenticated** and bind to `127.0.0.1` by default.
  Only set `host` to `0.0.0.0` on a trusted network; there is no access control.
- Optional outbound features are **off by default**: off-chain metadata fetch,
  IPFS-image resolution, and webhook sinks only make network requests when you
  configure them. Point them only at endpoints you trust.
- The indexer serves only what it read from your node; it does not execute
  transactions or scripts.
