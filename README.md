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
For a map of the moving parts, see [How it works](#how-it-works-the-architecture).
And because it was built as a step-by-step, test-driven **course**, you can also
read it chapter by chapter - see [The course](#the-course).

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

## How it works (the architecture)

The design is a straight pipeline - **source -> decode -> indexers -> store** - with
a query layer reading the store and an event bus tapping the stream. Here is the
whole journey of a single block, and which module owns each step.

### The life of a block

1. **The wire.** A `cardano-node` speaks the Ouroboros node-to-client protocol over
   a local socket: several independent "mini-protocols" multiplexed onto one
   connection. `mux.py` frames and routes them; each mini-protocol is its own small
   module (see the table). `chainsync.py` is the one that streams blocks.
2. **The source.** `source.py` defines a `ChainSource` interface - "give me the next
   `RollForward` / `RollBackward`" - so the rest of the code never touches wire
   bytes. There are two implementations: `node.py` (our own hand-written client) and
   `ogmios.py` (a bridge to the Ogmios server, used early in the course).
3. **Decode.** A block arrives as CBOR. `cbor_blocks.py` decodes it into the plain,
   typed values in `model.py` (`Block`, `Tx`, `TxOut`, certificates, and so on) -
   hashing bytes exactly so ids match the real chain.
4. **The follower.** `follow.py` is the sync loop. On start it **resumes** (agrees
   with the node on the newest block they share), then pulls events forever: a
   `RollForward` is indexed, a `RollBackward` runs the reorg engine. It keeps a
   running tally (that is the terminal progress line).
5. **The indexers.** `indexers.py` is a pipeline of small, single-purpose writers -
   one for outputs and balances, one for certificates, one for governance, one for
   mints, and so on. Each turns a decoded block into rows. New data domains are new
   indexers; which optional ones run is the `features` config.
6. **The store.** `store.py` owns the schema, the versioned migrations, and every
   query. `SqliteStore` is the default; `postgresstore.py` is the same logic over
   Postgres through a thin adapter. Both sit behind one `Store` interface, so the
   API, CLI, and explorer neither know nor care which is in use.
7. **The reorg engine.** The genuinely hard part, and it lives in the store's
   `rollback_to`: every indexed row carries a `block_id`, so undoing a fork is
   "delete the rows above block X, leaf table first". New tables roll back for free
   because they follow the same rule.

### Reading it back, and the live stream

- **`event.py`** is an event bus. As the follower indexes, it publishes typed events
  (a block, a delegation, a rollback). Consumers subscribe; today the live view is
  one, and webhooks are being added.
- **`api.py`** is the REST API (FastAPI): Blockfrost-shaped endpoints over the store,
  including a kupo-style `/matches/{pattern}` output lookup.
- **`explorer.py`** serves the browsable web explorer; **`live.py`** adds the `/live`
  WebSocket page (fed by the event bus) and is also the all-in-one runner that wires
  the follower, the store, and the server together.
- **`cli.py`** is the `chainidx` command line for one-off queries and node actions.
- **`localstate.py`**, **`mempoolclient.py`**, **`txsubmitclient.py`** use the other
  mini-protocols to read live ledger state, watch the mempool, and submit
  transactions.

### The five mini-protocols (all hand-written)

| Module | Mini-protocol | What it does |
| --- | --- | --- |
| `handshake.py` | handshake | negotiate the protocol version on connect |
| `chainsync.py` | chain-sync | stream blocks (RollForward / RollBackward) |
| `statequery.py` | local-state-query | read current ledger state (stake, params) |
| `txsubmit.py` | local-tx-submission | submit a signed transaction to the node |
| `txmonitor.py` | local-tx-monitor | inspect the node's mempool |

### The four design seams

These are the extension points the whole thing is built around, so it can grow
toward db-sync without rewrites:

1. **Block-keyed rollback** - every row has a `block_id`; reorgs delete by it.
2. **A pluggable indexer pipeline** - new data domains are new indexer modules.
3. **A `Store` interface** - SQLite or Postgres behind the same methods.
4. **An event bus** - indexers publish; the live view and webhooks consume.

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

That is enough to run against a node using **SQLite**. If you want Postgres instead,
you will install one more package in [Step 3](#step-3---start-the-indexer) - it is a
choice you make there, not extra setup now.

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
- **`db_path`** - where the SQLite database file goes (`chain.db` is fine). It is
  created on first run; delete it to start indexing from scratch.

> **One rule about paths:** every relative path here - `db_path`, `genesis_path`,
> even the `config.json` you pass to `CHAINIDX_CONFIG` - is resolved from **the
> directory you launch the command in**, not from where the file sits. So a bare
> `chain.db` launched from the repo becomes `chain-indexer/chain.db`. If you would
> rather not think about it, use absolute paths like `/var/lib/chainidx/chain.db`.

### Step 3 - start the indexer

The indexer stores into one of two databases: **SQLite** (the default, nothing to
install) or **Postgres** (for scale and shared readers). Pick one below - they use
the exact same code and give the exact same explorer, so you can switch later by
editing a single config field. If you are not sure, use SQLite; the
[Choosing a database](#choosing-a-database-sqlite-or-postgres) section explains why.

**Option A - SQLite (default, zero setup):** you already have everything. Just start
it:

```bash
CHAINIDX_CONFIG=config.json python -m chainidx.live
```

**Option B - Postgres:** install the driver and create an empty database (the
indexer makes the tables itself), then point the config at it:

```bash
pip install -e ".[chain,postgres]"   # the Postgres driver
createdb chainidx                     # an empty database
```

Add `postgres_dsn` to your `config.json` - when it is present, Postgres is used and
`db_path` is ignored - then start it with the same command as Option A:

```json
{
  "socket_path": "/path/to/node.socket",
  "network_magic": 42,
  "genesis_path": "/path/to/shelley-genesis.json",
  "postgres_dsn": "dbname=chainidx"
}
```

That bare `dbname=chainidx` works for a local, password-less server on the default
port. For anything else, the DSN is a standard PostgreSQL (libpq) connection string,
so it already carries whatever your server needs - no code changes:

```json
{ "postgres_dsn": "host=db.example.com port=5544 dbname=chainidx user=alice password=secret sslmode=require" }
```

- **`host`** / **`port`** - where the server is (omit for local on port `5432`).
- **`user`** / **`password`** - the login (omit if your server trusts you without a
  password, like a local peer-authenticated setup).
- **`sslmode=require`** - for a remote server that expects TLS.

> **Keeping the password out of the file.** Every setting can also come from an
> environment variable, which wins over the file. So leave the password out of
> `config.json` and pass the DSN at start time:
> `CHAINIDX_POSTGRES_DSN="host=... password=secret" CHAINIDX_CONFIG=config.json python -m chainidx.live`.
> (libpq's own `PGPASSWORD` and `~/.pgpass` work too - it is a normal PostgreSQL client.)

**Whichever you chose,** that one command does everything: it connects to the node,
follows the chain from the beginning, writes blocks down, and serves the explorer.
Leave it running - it keeps following the tip and rolls back automatically if the
chain forks. You will see one startup line, then a progress summary every ten
seconds:

```
live view on http://127.0.0.1:8000/live
following the chain: tip block #14210, 14210 applied, 0 rolled back
following the chain: tip block #14257, 14257 applied, 0 rolled back
```

The per-block detail is in the browser; the terminal line is just so you can see it
is alive and how far it has caught up (and, if the chain forks, the "rolled back"
count ticks up). Press **Ctrl-C** to stop it; restart the same command any time and
it resumes from where the database left off.

### Step 4 - open the explorer

Open **http://127.0.0.1:8000/** in your browser (the same page whichever database
you chose). Blocks and transactions appear as the indexer catches up. The
**live view** at **http://127.0.0.1:8000/live** shows new blocks arriving (and
reorgs rolling back) in real time.

> Syncing from genesis takes a while on a busy network. On a local fast cluster it
> is a few minutes; on mainnet a full from-genesis sync is slow (see
> [Choosing a database](#choosing-a-database-sqlite-or-postgres)).

That is the whole thing. Everything below is optional.

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

## Running more than one network at once

You can follow several networks in parallel - say preprod **and** preview - by
giving each its own **database** and its own **port**. Nothing is shared and nothing
is overwritten.

> **Important:** each network needs its own `db_path` (or `postgres_dsn`). The
> database is not tagged with a network, so pointing two different networks at the
> same database would mix their blocks into one corrupt index. Keep them separate.

One config file per network:

```jsonc
// preprod.json
{ "socket_path": "/preprod/node.socket", "network_magic": 1,
  "genesis_path": "/preprod/shelley-genesis.json", "db_path": "preprod.db", "port": 8000 }

// preview.json
{ "socket_path": "/preview/node.socket", "network_magic": 2,
  "genesis_path": "/preview/shelley-genesis.json", "db_path": "preview.db", "port": 8001 }
```

Then start one indexer per network, each in its own terminal:

```bash
CHAINIDX_CONFIG=preprod.json python -m chainidx.live   # explorer on http://127.0.0.1:8000/
CHAINIDX_CONFIG=preview.json python -m chainidx.live   # explorer on http://127.0.0.1:8001/
```

The `host` and `port` fields (default `127.0.0.1` and `8000`) control where each
explorer listens; give each network a different port so they do not collide. Setting
`host` to `0.0.0.0` exposes an explorer to your network - only do that on a trusted
one, as there is no authentication.

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

## Troubleshooting

First-run problems are almost always the node connection or the config, not the
indexer. The most common ones:

- **It exits immediately with a connection error.** The node is not running, or
  `socket_path` is wrong. Check the node is up and that the path matches its
  `--socket-path` exactly (the same value you would use for
  `CARDANO_NODE_SOCKET_PATH`). The socket is a file - `ls` it to be sure it exists.
- **The explorer loads but stays empty, and the terminal count sticks at 0.** The
  follower connected but no blocks are arriving. Usually the node itself is not
  synced yet (give it time), or you are pointed at a node that has no chain. If the
  `following the chain: ... applied` count is climbing, it is working - the explorer
  just fills in as it catches up.
- **`address already in use` on startup.** Something is already on the port
  (probably another indexer on `8000`). Set a different `port` in the config, or
  stop the other one. See [Running more than one network](#running-more-than-one-network-at-once).
- **Dates, epochs, or slots look wrong.** `network_magic` and `genesis_path` are for
  different networks. They must match the network your node is on - magic `1` with
  the preprod genesis, `2` with preview, and so on.
- **`ModuleNotFoundError: psycopg` (Postgres).** The driver is not installed. Run
  `pip install -e ".[chain,postgres]"`.
- **How do I stop it, and does it run forever?** It follows the tip forever; press
  **Ctrl-C** to stop. Restarting the same command resumes from the database - safe
  to do any time.
- **How do I start indexing from scratch?** Stop it, then delete the database: the
  SQLite file (`rm chain.db`), or for Postgres `dropdb chainidx && createdb chainidx`.
  Start it again and it re-syncs from the beginning.

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
simplified subset of db-sync's tables. The `/matches/{pattern}` endpoint answers the
"find the UTxOs matching this address or policy" question that
[kupo](https://github.com/CardanoSolutions/kupo) is built for, reusing the index we
already keep.

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
  mini-protocols; a JSON config with feature toggles; the Postgres backend; a
  kupo-style watch/matches API; and running several networks at once.

Each chapter's `README.md` explains the one idea it adds and why.

## License

MIT. See [LICENSE](LICENSE).
