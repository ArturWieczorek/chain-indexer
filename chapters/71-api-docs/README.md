# Chapter 71 - Industry-style API documentation

> **Goal:** make the REST API self-documenting and try-it-live, and add a written
> reference that shows every endpoint with a real example request and output.

## Two kinds of docs, for two moments

- **Interactive (Swagger UI), for exploring.** The API is built with FastAPI, so an
  OpenAPI schema and a Swagger UI come for free at `/docs` (and ReDoc at `/redoc`).
  Swagger's **Try it out** runs each endpoint live against your own node - the
  fastest way to see real data. The explorer header now has an **API** link
  straight to it.
- **Written (docs/API.md), for reading.** A comprehensive reference with a real
  example request and a full, formatted, explained example response for every
  endpoint - the thing you read to understand what the API offers before you start
  clicking.

## Making Swagger worth opening

FastAPI generates the schema, but a good page needs a few touches, so `create_app`
now sets a real `title`, a `description` that points at `/redoc`, the explorer, and
`docs/API.md`, and the `version` read from the installed package metadata (one
source of truth, the `pyproject.toml` version). The two headline kupo-style
endpoints, `/matches/{pattern}` and `/datums/{hash}`, carry a `summary` and a filled
response **example**, so Swagger shows a realistic body rather than a bare schema.

## The written reference

`docs/API.md` documents all the endpoints, grouped (meta, blocks, transactions,
addresses and accounts, assets and policies, the kupo-style watch/matches and
datums, pools, governance, certificates and withdrawals, analytics, epochs,
mempool), plus a **Webhooks** section with the exact event payloads (`block`,
`transaction`, `rollback`) that get POSTed. Each endpoint has a `curl` example and a
real JSON response, captured from the code so the field names are exact.

## What we built

- An **API** link in the explorer header to the interactive Swagger UI.
- Richer OpenAPI metadata (title, version, description) and filled examples on the
  watch/matches and datums endpoints.
- `docs/API.md`, the full written reference with examples and outputs.

## Commit and tag

```bash
git add -A
git commit -m "docs(ch71): interactive Swagger link and a full written API reference"
git tag ch71
```
