# Chapter 52 - Asset images

> **Goal:** render an NFT's image on its asset page, when its metadata carries one
> - resolving `ipfs://` references through a gateway the operator configures.

CIP-25 and CIP-68 metadata (chapters 46-47) often include an `image` field. It is
usually an `ipfs://` URI, which a browser cannot load directly; it needs an IPFS
gateway. Which gateway (if any) to use is an operator choice, so it is
configuration, not something baked in.

## Configuration, exposed to the client

`create_app` gains an optional `ipfs_gateway`, and a new `/config` endpoint returns
it (`{"ipfs_gateway": ...}`, null by default). The live runner reads it from
`CHAINIDX_IPFS_GATEWAY`. The explorer fetches `/config` and, on an asset page with
an `image`, resolves it:

- `http(s):` and `data:` URLs are used as-is,
- `ipfs://<cid>` becomes `<gateway>/<cid>` when a gateway is set (otherwise the
  image is simply not shown, and the raw value still appears in the metadata
  table),

then renders an `<img>`. An image reference split across an array of chunks (as
CIP-25 allows for long URLs) is joined first.

## Test first (red), make it pass (green)

An API test checks `/config` returns null by default and the configured gateway
when set. The image resolution itself is client-side. `make check` stays green and
fully covered.

## What we built

- `ipfs_gateway` config threaded through `create_app`/explorer/live from
  `CHAINIDX_IPFS_GATEWAY`; a `/config` endpoint.
- An image panel on the asset page, resolving `ipfs://` through the gateway.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch52): render asset images via a configurable ipfs gateway"
git tag ch52
```

## Next up

UI polish: favicons, and a dark/light theme with colour selection.
