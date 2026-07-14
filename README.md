# chain-indexer

[![CI](https://github.com/ArturWieczorek/chain-indexer/actions/workflows/ci.yml/badge.svg)](https://github.com/ArturWieczorek/chain-indexer/actions/workflows/ci.yml)

A mini Cardano chain indexer and block explorer, done seriously.

This is "cardano-db-sync, but tiny and mine": a program that follows a Cardano
node, writes its blocks and transactions into a database, and - the genuinely hard
part - **undoes that state correctly when the chain reorganizes**. On top of the
engine sit a REST query API, a command-line tool, and a browsable block explorer
with a live view.

It talks to the node over the Ouroboros wire protocols **written by hand** (all
five node-to-client mini-protocols), so it needs no middleware - just a running
`cardano-node`. It works on a local test cluster, on preprod/preview, and on
mainnet, and it can store into either **SQLite** (zero setup) or **Postgres** (for
scale).

If you just want to run it, jump to [Getting started](#getting-started-from-zero).
If you want to understand how it is built, it is also a step-by-step, test-driven
**course** - see [The course](#the-course).

## What it looks like

The explorer is a single web page that covers what a professional explorer shows:

- **Blocks**, **Transactions** (with Summary / UTXOs / Metadata tabs), and a
  **Mempool** (pending transactions, live from the node);
- **Epochs**, **Pools** (full on-chain details, delegators, blocks and stake
  charts), **Accounts** (delegation, rewards, controlled stake);
- **Governance** (actions with vote tallies, DReps, the constitutional committee,
  protocol parameters and updates);
- **Certificates** (every Conway certificate kind), **Withdrawals**;
- **Tokens** with CIP-25 and CIP-68 metadata (and images), per-policy pages, and a
  mint-transactions list;
- **Analytics**: transactions/blocks/fees over time, top addresses and stake
  accounts.

Everything is clickable and cross-linked, and there is a dark/light theme.

## What it is (in one picture)

```
      a Cardano node                    chain-indexer                    you
   (the source of truth)         (a faithful, reorg-aware follower)
          |                                                             |
          |  "here is the next block"   +----------------------+       |
          |  (RollForward) ------------>|  decode the block    |       |
          |                             |         v            |       |
          |                             |  [ indexers ]        |       |
          |                             |         v            |       |
          |                             |  SQLite / Postgres   |--REST->|  API + CLI
          |  "back up to block X!"      |         v            |       |
          |  (RollBackward) ----------->|  ROLL BACK the index |--WS -->|  explorer
          |                             +----------------------+       |  (live view)
```

The node sends two kinds of message. `RollForward` hands over the next block, and
the indexer writes it down. `RollBackward` says "the last few blocks were not
final, throw them away" - and the indexer must undo exactly the right rows. Both
come from the chain-sync mini-protocol.

---

## Getting started from zero

This walks you from "I have a `cardano-node` running" to "I have an indexer and an
explorer in my browser". No prior indexer experience assumed.

### Step 0 - what you need before you start

1. **A running `cardano-node`.** It can be a local test cluster, or a node synced
   to preprod, preview, or mainnet. You do not configure the node here; you only
   need two things from it:
   - the **socket path** it is listening on (the node's `--socket-path`), and
   - the **Shelley genesis file** for the network the node is on (the
     `shelley-genesis.json` the node was started with).
2. **Python 3.12 or newer.** Check with `python3 --version`.
3. That is it for SQLite. For Postgres you also need a running PostgreSQL server
   (any recent version) and permission to create a database.

If you do not have a node and just want to try it, the easiest way to get one is a
local cluster with [cardonnay](https://github.com/mkoura/cardonnay)
(`cardonnay create -t conway_fast`), which prints the socket and genesis paths for
you.

### Step 1 - get the code and install it

```bash
git clone https://github.com/ArturWieczorek/chain-indexer.git
cd chain-indexer

python3 -m venv .venv
source .venv/bin/activate

# install the app and the libraries it needs to talk to a node
pip install -e ".[chain]"
```

That is enough to run against a node using **SQLite**. (For Postgres, see
[Step 3b](#step-3b---postgres-instead).)

### Step 2 - write a config file

The indexer is driven by one small JSON file. Create `config.json` next to the
repo (change the paths to match your node):

```json
{
  "socket_path": "/path/to/node.socket",
  "network_magic": 42,
  "genesis_path": "/path/to/shelley-genesis.json",
  "db_path": "chain.db"
}
```

- **`socket_path`** - the node's socket (the same value you would put in
  `CARDANO_NODE_SOCKET_PATH`).
- **`network_magic`** - which network the node is on:
  - local cluster: usually `42`
  - preview: `2`
  - preprod: `1`
  - mainnet: `764824073`
- **`genesis_path`** - the network's `shelley-genesis.json` (used to turn slots
  into dates and epochs).
- **`db_path`** - where the SQLite database file goes. `chain.db` is fine.

### Step 3 - start the indexer (SQLite)

```bash
CHAINIDX_CONFIG=config.json python -m chainidx.live
```

That one command does everything: it connects to the node, follows the chain from
the beginning, writes blocks into `chain.db`, and serves the explorer. Leave it
running - it keeps following the tip and will roll back automatically if the chain
forks. You will see:

```
live view on http://127.0.0.1:8000/live
```

### Step 4 - open the explorer

Open **http://127.0.0.1:8000/** in your browser. Blocks and transactions appear as
the indexer catches up. The **live view** at **http://127.0.0.1:8000/live** shows
new blocks arriving (and reorgs rolling back) in real time.

> Syncing from genesis takes a while on a busy network. On a local fast cluster it
> is a few minutes; on mainnet a full from-genesis sync is slow (see
> [Choosing a database](#choosing-a-database-sqlite-or-postgres)).

That is the whole thing. Everything below is optional.

### Step 3b - Postgres instead

If you want Postgres rather than SQLite (see the next section for why):

```bash
# 1. install the Postgres driver as well
pip install -e ".[chain,postgres]"

# 2. create an empty database (the indexer creates the tables itself)
createdb chainidx
```

Then set `postgres_dsn` in your `config.json` (when it is present, Postgres is used
and `db_path` is ignored):

```json
{
  "socket_path": "/path/to/node.socket",
  "network_magic": 42,
  "genesis_path": "/path/to/shelley-genesis.json",
  "postgres_dsn": "dbname=chainidx"
}
```

Start it the same way: `CHAINIDX_CONFIG=config.json python -m chainidx.live`. The
DSN is a standard libpq connection string, for example
`"host=localhost port=5432 dbname=chainidx user=me password=secret"`.

---

## Choosing a database: SQLite or Postgres

**Short version: use SQLite unless you have a specific reason not to.**

| | SQLite (default) | Postgres |
| --- | --- | --- |
| Setup | none - a file appears | install server, `createdb`, driver |
| Speed (local/testnet) | fastest (in-process) | slower (client-server round-trips) |
| Concurrent readers, sharing | limited | strong |
| Mainnet-scale volume | works but a huge file | the right tool |
| When to pick it | local cluster, preprod, learning, one machine | many readers, a team, big data |

Both use the exact same code and expose the exact same explorer and API - only the
storage differs. You can switch by editing one config field.

**A note for mainnet.** The code runs on mainnet unchanged (just the mainnet
socket, magic `764824073`, and genesis). Tip-following is fine. A full
**from-genesis** mainnet sync, however, is slow here: the indexer inserts row by
row, whereas db-sync uses bulk loading. So chain-indexer is ideal for local
clusters and testnets, and for watching mainnet from a recent point; it is not
trying to be a fast full-history mainnet indexer.

---

## Optional features

These are off by default. Turn them on in `config.json` (or with the matching
environment variable).

```json
{
  "fetch_metadata": true,
  "ipfs_gateway": "https://ipfs.io/ipfs/",
  "stake_history": true,
  "features": { "governance": true, "mints": true, "assets": true }
}
```

- **`fetch_metadata`** (`CHAINIDX_FETCH_METADATA`) - fetch a pool's off-chain
  metadata (name, ticker) from its registered URL. Off by default so the indexer
  never touches the network on its own.
- **`ipfs_gateway`** (`CHAINIDX_IPFS_GATEWAY`) - render NFT images by resolving
  `ipfs://` links through this gateway.
- **`stake_history`** (`CHAINIDX_STAKE_HISTORY`) - record each epoch's live stake
  so the pool page can chart stake and expected-vs-made blocks over time. It only
  fills going forward (the node cannot be asked for past epochs).
- **`features`** - which optional indexers run, like db-sync's `insert_options`.
  Names: `certificates`, `governance`, `withdrawals`, `assets`, `mints`. A name
  left out defaults to on; set one to `false` to skip indexing it. The core
  block/transaction/output indexing is always on.

Every setting can also be given as an environment variable, and the environment
always wins over the file - handy for a one-off override without editing the config.

---

## Using the command line

Besides the all-in-one `python -m chainidx.live`, there is a `chainidx` CLI for
one-off queries and actions. Point it at a database (or a live node) and ask:

```bash
# queries against the indexed database
chainidx --db chain.db tip                 # the latest indexed block
chainidx --db chain.db pools               # registered pools
chainidx --db chain.db balance <address>   # an address balance

# read live ledger state from the node (local-state-query)
chainidx state --socket /path/to/node.socket --magic 42

# submit a signed transaction to the node, over our own protocol
chainidx submit tx.signed --socket /path/to/node.socket --magic 42
```

You can also run just the follower, or just the explorer, if you prefer them
separate - see `chainidx --help`.

---

## What it indexes, and what it does not

**It indexes** everything that arrives on-chain, reorg-aware: blocks and
transactions; outputs, inputs, native assets and address balances; the full set of
Conway certificates; governance (DReps, votes, actions, committee); withdrawals;
mints; and CIP-25 / CIP-68 token metadata.

**Live ledger state** (current live stake, saturation, protocol parameters, reward
balances) is read from the node over local-state-query, not replayed from blocks,
so it is correct whenever queried.

**It does not** recompute reward amounts or ROS per epoch. Those come from the
ledger's reward calculation across epoch boundaries, which no wire protocol carries
and which we do not reimplement. Stake and expected-blocks trends are shown (from
the stake history you opt into); reward/ROS history is deliberately not faked. See
[chapter 18](chapters/18-design-and-tradeoffs/) for the full boundary.

---

## Where this sits in the real world

The professional versions of this idea are
[cardano-db-sync](https://github.com/IntersectMBO/cardano-db-sync) (the reference
Postgres indexer) and [Dolos](https://github.com/txpipe/dolos) (a lightweight
"Cardano data node"). This project is a teaching-sized cousin: small enough to read
in an afternoon, honest about what it does and does not do. The REST API borrows
its endpoint shapes from [Blockfrost](https://blockfrost.io); the schema is a
simplified subset of db-sync's tables.

---

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
make install     # editable install with the chain libraries and dev tools
make check       # linter, type checker, and tests - exactly what CI runs
```

`make check` is green at every release. The unit tests are fully offline and
deterministic (100 percent coverage on the pure core); the integration tests (a
real handshake, follows via Ogmios and via our own protocol, and a forced rollback)
run only when a node socket is present.

---

## The course

The project was built as a test-driven course, one commit per chapter, each tagged
`chNN` with its own write-up in [`chapters/`](chapters/). Reading the chapters in
order (and checking out each tag) turns the git history into the lesson plan.

- **ch00-ch19** build the core: the block/chain model, the SQLite store, indexing,
  the headline reorg engine, Shelley staking and Conway governance, the Ogmios and
  then the hand-written Ouroboros wire protocols, the REST API, CLI, explorer, live
  view, and a forced-reorg drill on a real cluster. Tagged `v1.0.0`.
- **ch20 onward** grow it toward a professional explorer: local-state-query and
  epochs; pools, accounts, and rewards; a full governance section; analytics;
  tokens with CIP-25/68 metadata and images; the mempool and transaction-submission
  mini-protocols; a JSON config with feature toggles; and the Postgres backend.

Each chapter's `README.md` explains the one idea it adds and why.

## License

MIT. See [LICENSE](LICENSE).
