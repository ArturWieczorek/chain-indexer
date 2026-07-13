# Chapter 15 - The explorer

> **Goal:** a browsable block explorer. A single web page over the REST API where
> you click from the latest blocks into a block, into its transactions, into an
> address - the cardanoscan-style view of the data we index.

The API answers questions if you know the URL to ask. An explorer turns that into
something you can browse: land on the latest blocks, click one, read its
transactions, follow an output to an address, see the balance. Same data, human
shape.

## One static page, no build step

The explorer is a single HTML file (`web/index.html`) with inlined CSS and a bit
of vanilla JavaScript. No framework, no bundler, nothing to install. It talks to
the API we already built using the browser's `fetch`:

```
   browser                         our server (chapter 13 API + one route)
   -------                         ----------------------------------------
   GET /                 ------->   serves web/index.html
   fetch("/blocks?..")  ------->   JSON
   fetch("/blocks/HASH")------->   JSON
   fetch("/txs/HASH")   ------->   JSON
   fetch("/addresses/A")------->   JSON
```

`explorer.py` is tiny: it takes the API app and adds exactly one route, `GET /`,
that returns the page. Everything else the page needs is already an endpoint. That
is the reward for having built a clean read API first - the UI is a thin client
over it.

## Client-side routing

The page uses the URL fragment (the part after `#`) to decide what to show,
without ever reloading:

```
  #/                    -> latest blocks
  #/block/<hash>        -> one block and its transactions
  #/tx/<hash>           -> a transaction's inputs and outputs
  #/address/<addr>      -> an address's balance and unspent outputs
```

A `hashchange` listener re-renders when the fragment changes, and every hash,
address, and transaction id on the page is a link to another fragment. So clicking
around never hits the server for HTML - only for JSON. The search box guesses what
you typed (an address, or a 64-character block hash) and navigates to the right
fragment.

## What you see

- **Home**: the latest blocks (height, slot, hash, tx count), newest first, with
  the current tip shown in the header.
- **Block**: its hash, slot, previous block (a link), and the list of its
  transactions.
- **Transaction**: its inputs (each a link back to the spending transaction) and
  its outputs (each address a link, each value in ada).
- **Address**: its balance and its unspent outputs, including any native assets.

Run against a real followed database, it browses the actual chain: the latest
blocks are real, clicking a block shows its real transactions, and following an
output lands on a real address balance.

## A note on serving static files

We embed the page's bytes at import (`Path(...).read_text()`) and return them from
the `/` route as an `HTMLResponse`. For one small page that is simplest. A larger
app would mount a static-files directory instead; the idea is the same.

## Test first (red), make it pass (green)

The test serves the app with a `TestClient` and checks that `GET /` returns the
HTML page and that the API routes (like `/health`) are still mounted underneath
it. The page's JavaScript is exercised by opening it in a browser (`make
explorer`); the test pins the wiring. `make check` stays green and fully covered.

## What we built

- `web/index.html`: a single-page block explorer in vanilla JavaScript.
- `chainidx.explorer.create_explorer_app`: the API plus the page at `/`.
- `make explorer` to serve it over a real database.

## Glossary

- **Explorer**: a UI for browsing a blockchain's blocks, transactions, and
  addresses.
- **`fetch`**: the browser API for making HTTP requests from JavaScript.
- **URL fragment / hash routing**: using the part after `#` to drive a
  single-page app without reloading.
- **`HTMLResponse`**: a FastAPI response that sends HTML instead of JSON.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch15): add the browsable block explorer UI"
git tag ch15
```

## Next up

[Chapter 16 - Live view and analytics](../16-live-view-and-analytics/): the
explorer shows what happened; now we show what is happening. A WebSocket streams
new blocks as they are indexed, a small dashboard tracks transaction volume and
large movements, and - the payoff of the whole project - a reorg visibly rolls the
state back in front of you.
