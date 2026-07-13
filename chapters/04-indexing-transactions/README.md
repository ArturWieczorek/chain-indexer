# Chapter 04 - Indexing transactions

> **Goal:** index what is *inside* transactions - outputs, inputs, and native
> assets - and answer the first real question a chain database exists for: what
> is an address's balance? Along the way we introduce the pluggable indexer
> pipeline (design seam number two).

Chapter 03 stored blocks and a list of transaction hashes. That is not yet
useful: nobody asks "what transactions exist?" They ask "how much does this
address hold?" To answer that we have to understand how value moves on Cardano.

## The UTxO model in ninety seconds

Cardano does not keep account balances the way a bank does. Instead, value lives
in **unspent transaction outputs** (UTxOs). It works like physical cash:

- A transaction **output** is a banknote: an amount of value with an owner (an
  address). Once created it just sits there, "unspent".
- A transaction **input** spends a whole earlier output, like handing over a
  banknote. You cannot spend half of one; you consume it entirely and produce new
  outputs (including change back to yourself).

```
  tx1                                  tx2 (spends tx1's output 0)
  +-----------------------+            +-------------------------------+
  | inputs:  (from before)|            | inputs:  tx1 #0  (5 ada)      |
  | outputs: #0 alice 5ADA|----------->| outputs: #0 bob   3 ada       |
  +-----------------------+  consumes  |          #1 alice 2 ada (change)|
                                       +-------------------------------+
```

So an address's balance is simply: **the sum of the outputs it owns that have not
yet been consumed.** Index outputs, track which are consumed, and balances fall
out for free.

## The pipeline: one indexer per concern

We could cram all this into the store's `apply_block`. Instead we split it into
**indexers**, each owning one concern, and have the store hand every transaction
to each indexer in turn:

```
  apply_block(block)
     |
     +-- insert the block row
     +-- for each tx in the block:
            insert the tx row
            for each indexer:            <--- the pipeline
                indexer.index_tx(...)
```

This chapter has two indexers:

- `OutputIndexer` writes a `tx_out` row per output (address, lovelace) and a
  `ma_tx_out` row per native asset on it.
- `InputIndexer` writes a `tx_in` row per input and marks the consumed output as
  spent.

Adding staking in chapter 06 and governance in chapter 07 will mean writing new
indexers and adding them to the list - the store, the sync loop, and the rollback
engine never change. That is the second design seam.

> **Why order matters.** Outputs are indexed before inputs. Within a single block
> a later transaction can spend an output created by an earlier one, so the
> output must already be in the table when we process the spend. The list
> `(OutputIndexer(), InputIndexer())` encodes that ordering.

## Marking an output spent

How do we track "consumed"? Each `tx_out` row has a nullable `consumed_by_tx_id`.
It starts `NULL`. When an input spends that output, we stamp it with the spending
transaction's id:

```sql
UPDATE tx_out SET consumed_by_tx_id = ?
WHERE index_no = ? AND tx_id = (SELECT id FROM tx WHERE hash = ?)
```

A balance is then one query:

```sql
SELECT SUM(lovelace) FROM tx_out
WHERE address = ? AND consumed_by_tx_id IS NULL
```

This "mark, do not delete" approach is deliberate and important for chapter 05:
because spending only *sets a column* rather than deleting a row, a rollback can
undo a spend by clearing that column again. If we had deleted consumed outputs we
would have nothing to restore.

> **Every table carries `block_id`.** `tx_out`, `ma_tx_out`, and `tx_in` all
> record the block they came from, directly. It is slightly denormalized (you
> could reach the block through `tx`), but it means the rollback engine can undo
> a block with one uniform `DELETE ... WHERE block_id >= ?` per table. That
> uniformity is the whole trick of chapter 05.

## Test first (red)

The tests read like little stories about money moving:

```python
def test_spending_an_output_removes_it_from_the_balance() -> None:
    store = SqliteStore()
    store.apply_block(blk(1, "b1", "genesis", (Tx("tx1", outputs=(TxOut("alice", 5_000_000),)),)))
    assert store.balance("alice") == 5_000_000

    spend = Tx("tx2", inputs=(TxIn("tx1", 0),),
               outputs=(TxOut("bob", 3_000_000), TxOut("alice", 2_000_000)))
    store.apply_block(blk(2, "b2", "b1", (spend,)))
    assert store.balance("alice") == 2_000_000
    assert store.balance("bob") == 3_000_000
```

There is also a test that an input referencing an output we never indexed (a
genesis output, say, when starting mid-chain) is harmless - it updates zero rows.

## Make it pass (green)

Migration 2 adds `tx_out`, `ma_tx_out`, and `tx_in`. The two indexers live in
`chainidx/indexers.py`; the store gains `balance` and `utxos`. `make check` stays
green and fully covered.

## What we built

- The indexer pipeline: `OutputIndexer` and `InputIndexer`, run per transaction.
- `tx_out` / `ma_tx_out` / `tx_in`, all block-keyed for easy rollback.
- Spend tracking by column, not deletion, so it can be undone.
- `balance(address)` and `utxos(address)` derived views.

## Glossary

- **UTxO**: unspent transaction output; the "cash" model Cardano uses.
- **Input / output**: an input consumes a whole earlier output; outputs create
  new value at addresses.
- **Change**: an output back to the sender, since inputs must be spent whole.
- **Indexer**: a module that writes one concern's rows for each transaction.
- **`consumed_by_tx_id`**: the column that records which transaction spent an
  output; `NULL` means unspent.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch04): index outputs, inputs, assets, and balances"
git tag ch04
```

## Next up

[Chapter 05 - Rollbacks and reorgs](../05-rollbacks-and-reorgs/): the headline.
The node says "back up to block X"; we make the database obey, deleting exactly
the right rows in the right order and restoring the outputs the rolled-back
blocks had spent. Everything so far was built so that this chapter can be short,
correct, and generic.
