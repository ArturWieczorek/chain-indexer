# Chapter 41 - Transactions section

> **Goal:** a Transactions view - a recent-transactions page and a latest
> transactions panel on the home page - so transactions are browsable in their own
> right, not only through the block that carries them.

Until now you reached a transaction through its block. Real explorers also list
transactions directly, newest first. This chapter adds that.

## A recent-transactions query

`store.recent_transactions` joins `tx` to its `block` and left-joins `tx_out` to
count and sum a transaction's outputs, newest first:

```sql
SELECT t.hash, t.fee, b.hash, b.block_no, b.slot_no,
       COUNT(o.id) AS out_count, COALESCE(SUM(o.lovelace), 0) AS out_total
FROM tx t JOIN block b ON b.id = t.block_id
LEFT JOIN tx_out o ON o.tx_id = t.id
GROUP BY t.id ORDER BY t.id DESC LIMIT ?
```

It returns a `TxSummary` per row - enough to render a list line (block, fee,
output count and total) without loading each transaction's full detail.

## API and explorer

- `/transactions` (with a `limit`) lists recent transactions; when network
  parameters are configured, each carries its `time`.
- The explorer gains a **Transactions** nav section and shows a **Latest
  transactions** panel on the home page under the latest blocks. Each row links to
  the transaction detail and to its block.

## Test first (red), make it pass (green)

API tests check the newest-first order, the per-transaction output count and total,
that `time` is absent without network parameters, and present with them. `make
check` stays green and fully covered.

## What we built

- `TxSummary` model; `store.recent_transactions`.
- `/transactions`; a Transactions page and a Latest-transactions panel on the home
  page.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch41): transactions section with recent transactions"
git tag ch41
```

## Next up

Richer analytics: time-series charts (transactions and blocks over time) and a
mempool view built on the local-tx-monitor mini-protocol.
