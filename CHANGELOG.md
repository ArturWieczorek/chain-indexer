# Changelog

All notable changes to this project are documented here. The format is loosely
based on Keep a Changelog. Each chapter tag (`chNN`) is a release of the course.

## [1.37.0] - Per-epoch stake history (opt-in)

### Added

- Migration 18 `stake_history`; `store.record_stake_history` /
  `store.pool_stake_history`; the snapshot loop records per-epoch live stake when
  `CHAINIDX_STAKE_HISTORY` is set.
- `/pools/{id}` returns `stake_history`; the pool page shows a live-stake-per-epoch
  chart.

## [1.36.0] - Richer recent blocks on the pool page

### Changed

- `/pools/{id}` `recent_blocks` now returns full block records (height, epoch,
  slot, hash); the pool page shows them as a table instead of bare hashes.

## [1.35.0] - Favicons, theme, and colour

### Added

- Inline-SVG favicons for the explorer and live pages.
- A light theme (CSS-variable overrides), a dark/light toggle, and accent-colour
  swatches, persisted in localStorage and shared across both pages.

## [1.34.0] - Asset images

### Added

- `create_app` gains an `ipfs_gateway` (from `CHAINIDX_IPFS_GATEWAY`) and a
  `/config` endpoint exposing it.
- The asset page renders an image from CIP-25/68 metadata, resolving `ipfs://`
  through the configured gateway.

## [1.33.0] - Off-chain pool metadata

### Added

- `offchain.parse_pool_metadata` (pure) and opt-in `fetch_pool_metadata` (HTTP).
- `create_app` gains an injected `metadata_fetcher`; the pool endpoint returns
  off-chain name/ticker/homepage when enabled (`CHAINIDX_FETCH_METADATA`), shown
  on the pool page.

## [1.32.0] - Full pool on-chain details

### Added

- Pool registration decoding of VRF hash, owners, relays, and metadata hash
  (`_decode_relay`); `PoolRegistration`/`PoolSummary` fields; migration 17.
- `/pools/{id}` returns the full on-chain details (hex id, VRF, owners as stake
  addresses, relays, metadata hash) and a registration time; the pool page shows
  them plus a performance summary (lifetime blocks, avg blocks per epoch).

## [1.31.0] - Mint transactions

### Added

- `Tx.mint` and `_decode_mint` (transaction-body mint field, key 9); `MintRecord`;
  migration 16 `mint_event`; `MintIndexer`; `store.recent_mints`.
- `/assets/mints` and a Mint Transactions sub-tab in the Tokens section (mints and
  burns, with quantity sign and the minting transaction).

## [1.30.0] - Richer pool detail

### Added

- Pool `cost` and `metadata_url` decoded from the registration certificate;
  `PoolRegistration`/`PoolSummary` carry them; migration 15 stores them.
- `store.pool_blocks_by_epoch`; `/pools/{id}` returns cost, metadata URL, and a
  blocks-per-epoch series; the pool page shows a blocks-per-epoch chart.

## [1.29.0] - CIP-68 asset metadata

### Added

- `TxOut.datum` and inline-datum decoding; `decode_cip68_datum`,
  `reference_asset_name`, and CIP-67 label constants in `cbor_blocks`.
- Migration 14 (`tx_out.datum`); `OutputIndexer` stores inline datums;
  `store.cip68_metadata` resolves a user token via its reference token's datum.
- `/assets/{policy_id}/{asset_name}` falls back to CIP-68 metadata and reports a
  `metadata_standard`; the explorer names the standard on the metadata panel.

## [1.28.0] - CIP-25 asset metadata

### Added

- Migration 13 `asset_metadata`; `AssetMetadataIndexer` (reads transaction
  metadata label 721); `store.asset_metadata`.
- `metadata` on `/assets/{policy_id}/{asset_name}` and a CIP-25 panel on the asset
  page in the explorer.

## [1.27.0] - Submitting transactions (local-tx-submission)

### Added

- The final node-to-client mini-protocol, local-tx-submission (id 6):
  `SubmitResult`, the pure `txsubmit` codec, and the integration `TxSubmitClient`.
- A `chainidx submit` command that submits a signed transaction over our own
  protocol (accept, or the node's rejection reason) instead of via the cli. All
  five node-to-client mini-protocols are now hand-written.

## [1.26.0] - Protocol updates

### Added

- `store.protocol_updates` (governance actions of type ParameterChange or
  HardForkInitiation); `/governance/protocol-updates` and a Protocol updates page
  in the explorer.

## [1.25.0] - The mempool (local-tx-monitor)

### Added

- The fifth node-to-client mini-protocol, local-tx-monitor (id 9):
  `cbor_blocks.tx_id_of_bytes`, the pure `txmonitor` codec, `MempoolStatus`, and
  the integration `MempoolClient`.
- `create_app` gains an optional `mempool_source`; `/mempool` serves the live
  mempool (capacity, fill, pending transaction ids) on demand, and the explorer
  gains a Mempool section. The live runner wires in the real client.

## [1.24.0] - Analytics time series

### Added

- `EpochStats` model and `store.epoch_stats` (per-epoch block, transaction, and
  fee totals).
- `/analytics/timeseries`; a reusable `lineChart` helper and Transactions /
  Blocks / Fees per-epoch charts on the Analytics page (replacing the single bar
  chart).

## [1.23.0] - Transactions section

### Added

- `TxSummary` model and `store.recent_transactions` (newest first, with per-tx
  output count and total).
- `/transactions`; a Transactions nav section and a Latest-transactions panel on
  the home page, each row linking to the transaction and its block.

## [1.22.0] - Top addresses and staking accounts

### Added

- `AddressBalance` / `StakeAccountBalance` models; `store.top_addresses` /
  `store.top_stake_accounts`, ranking unspent outputs by address and by stake
  credential.
- `/top/addresses` and `/top/accounts`; Top-addresses and Top-staking-accounts
  tables on the Analytics page, each entry linking to its detail page.

## [1.21.0] - Reward withdrawals

### Added

- `Withdrawal` / `WithdrawalRecord` models, `Tx.withdrawals`, and
  `_decode_withdrawals` (tx body key 5).
- `WithdrawalIndexer`; migration 12 `withdrawal` table (rolls back with blocks);
  `store.withdrawals` / `store.withdrawals_for_tx`.
- `/withdrawals`, a Withdrawals section in the explorer, and withdrawals on the
  transaction page (reward account linking to its account).

## [1.20.0] - The constitutional committee

### Added

- `CommitteeMember` model; `store.committee_members` / `store.committee_member`,
  derived from the committee certificates indexed in chapter 34.
- `/governance/committee` and `/governance/committee/{cold_credential}`.
- A Committee page and per-member page in the explorer, linked from the governance
  section; committee voters on governance actions now link into it.

## [1.19.0] - Protocol parameters and transaction governance links

### Added

- Migration 11 `protocol_param`; `store.record_protocol_params` /
  `store.protocol_params`; the live snapshot loop records them;
  `/protocol-parameters` and a Protocol parameters page in the explorer.
- `store.proposals_for_tx` / `store.votes_for_tx`; `GovVoteRecord.gov_action_id`.
- The transaction page now renders proposals and votes as tables that link to
  their governance action, instead of plain text.

## [1.18.0] - Policy pages and readable asset names

### Added

- `PolicyDetail` model and `store.policy_detail`; `/policies/{policy_id}` lists the
  assets minted under a policy.
- `_asset_name_text` decodes asset names to printable UTF-8; asset responses now
  include `asset_name_text` alongside the hex `asset_name`.
- A Minting policy page in the explorer, policy links from the asset and Tokens
  pages, and decoded asset names in the UI.

## [1.17.0] - Transaction detail tabs

### Added

- `ResolvedInput` model and `Tx.fee`/`Tx.metadata`; `TxDetail` now carries the
  fee, metadata, resolved inputs, and asset-bearing outputs.
- Fee (body key 2) and transaction metadata (block auxiliary data, all three era
  shapes) decoding in `cbor_blocks`.
- Migration 10 (`tx.fee`, `tx.metadata`); `store.get_tx` resolves inputs to the
  value they spend and loads output assets; `store.certificates_for_tx`.
- Tabbed transaction page (Summary / UTXOs / Metadata) with linked certificates.

### Fixed

- Clicking an input that referenced a never-indexed output (a genesis/faucet
  UTxO) led to a 404; such inputs are now shown without a link.

## [1.16.0] - Certificates browser

### Added

- Full Conway certificate decoding (tags 0-18): `VoteDelegation`, `DRepUpdate`,
  `CommitteeAuthHot`, `CommitteeResignCold` models and `certificate_fields`.
- Migration 9 flat `certificate` table (rolls back with blocks);
  `store.certificates` and `store.certificate_summary`.
- `/certificates` (filterable by `cert_type`) and `/certificates/summary`; a
  Certificates section in the explorer with category filters and linked subjects.
- The home-page transaction count links to the block's transaction list.

## [1.15.0] - Clickable governance and epoch blocks

### Added

- `DRepVote` model; `store.drep_votes` (votes a DRep cast, with the action type,
  `Unknown` when the action is not indexed) and `store.blocks_in_epoch`.
- `/governance/dreps/{drep_id}` now returns the DRep's votes;
  `/epochs/{epoch_no}/blocks` lists an epoch's blocks.
- Explorer: a DRep detail page, DRep links from the governance page and from a
  vote's voter, and a clickable block list on the epoch page.

### Fixed

- Governance action links returned 404: an action id is `txid#index`, and the
  `#` clashed with URL-fragment routing and truncated the request path. Ids are
  now URL-encoded across links, the router, and API calls.

## [1.14.0] - Governance from CBOR

### Added

- `_decode_proposals`/`_decode_votes` in the CBOR block decoder (tx body keys 20
  and 19), so the node path indexes real governance proposals and votes.

## [1.13.0] - Tokens

### Added

- `AssetDetail` + `store.asset_detail`; `/assets/{policy_id}/{asset_name}` and a
  Tokens section in the explorer (list + per-asset detail with holder count).

## [1.12.0] - Analytics

### Added

- `store.total_transactions` and `/analytics/summary` (network totals); an
  Analytics page with summary tiles and an inline-SVG blocks-per-epoch chart.

## [1.11.0] - Controlled stake

### Added

- `stake_credential_of` + a `stake_cred` column on `tx_out` (migration 8);
  `store.controlled_stake`; `/accounts/{stake}` and the account page show
  controlled stake.

## [1.10.0] - Transaction detail

### Added

- `TxActivity` + `store.tx_activity`; `/txs/{hash}` and the explorer tx page now
  show certificates, governance proposals, and votes.

## [1.9.0] - Account links in the UI

### Added

- `store.pool_delegators`; `/pools/{id}` returns a bech32 reward address and a
  `delegators_list` of stake accounts.
- Clickable reward-address and delegator account links on the pool page.

## [1.8.0] - Accounts and rewards

### Added

- `AccountState` + the argument-carrying LSQ query
  `delegations_and_rewards_query`/`parse_delegations_and_rewards`;
  `LocalStateClient.account_states`.
- Migration 7 (`account_stat`) + `store.record_account_states`/`account_state`/
  `registered_stake_credentials`; the snapshot loop persists account state.
- Enriched `/accounts/{stake}` (decodes stake_test1..., delegation + rewards) and
  an explorer account page.

## [1.7.0] - Bech32 addresses

### Added

- `chainidx.bech32`: BIP-0173 encode/decode and `pool_to_bech32`/
  `address_to_bech32`, verified against cardano-cli.
- API renders pool ids, block issuers, and addresses as bech32 and accepts
  bech32 in `/pools/{id}` and `/addresses/{addr}`; explorer shows pool1.../
  addr_test1... and a block's minting pool.

## [1.6.0] - Live stake and saturation

### Added

- Migration 6 (`pool_stat`, `ledger_stat`) + `store.record_stake_distribution`;
  `live_stake` and `saturation` on `PoolSummary`, the API, and pool pages.
- `n_opt` in the protocol-params parser; a periodic local-state-query snapshot
  task in the live runner.

## [1.5.0] - Governance

### Added

- `GovActionSummary`/`GovVoteRecord`/`DRepSummary` and
  `store.governance_action_summaries`/`governance_action_votes`/`drep_summaries`.
- API `/governance/actions`, `/governance/actions/{id}`, `/governance/dreps`,
  `/governance/dreps/{id}`; a Governance section in the explorer.

## [1.4.0] - Pools

### Added

- Block `issuer` (minting pool id = blake2b-224 of the header issuer key),
  computed in the CBOR and Ogmios decoders and stored (migration 5).
- `PoolSummary` + `store.pool_summaries`/`pool_detail`/`recent_blocks_by_pool`
  (blocks minted, delegators, pledge, margin).
- API `/pools` (enriched) and `/pools/{id}`; a Pools section in the explorer.

## [1.3.0] - Epochs and the dashboard

### Added

- `chainidx.network.NetworkParams`: slot -> epoch -> wall-clock math, loaded from
  a Shelley genesis; `EpochSummary` + `store.epoch_summaries`/`epoch_summary`.
- API `/epochs`, `/epochs/{no}`, `/network`, and block timestamps (params from
  `CHAINIDX_GENESIS`).
- Explorer: nav bar, current-epoch banner with progress, an Epochs page, and
  block times.

## [1.2.0] - Local-state-query

### Added

- `chainidx.statequery`: a from-scratch local-state-query codec (acquire / query /
  release; era-wrapped ledger queries) with real captured result fixtures.
- `chainidx.localstate.LocalStateClient` (integration) reading a `LedgerSnapshot`
  (epoch, system start, protocol params, stake pools, live stake distribution).
- `chainidx state` CLI command; `LedgerSnapshot` / `PoolStake` models.

## [1.1.0] - Explorer search by height and slot

### Added

- API: `GET /blocks/height/{n}` and `GET /blocks/slot/{n}`, plus store methods
  `get_block_by_number` and `get_block_by_slot`.
- Explorer: the search box now accepts a block height, `slot:N`, a block or tx
  hash (resolved automatically), or an address; block heights and slots on the
  home page are clickable.

## [1.0.0] - Publish

The complete course: a reorg-aware Cardano chain indexer with a from-scratch
Ouroboros chain-sync client, a Blockfrost-style REST API, a CLI, and a browsable,
live-updating block explorer. Chapters ch00 through ch19; `make check` green at
every tag; 100 percent coverage on the pure-logic core.

## [ch19] - Publish

### Changed

- README chapter table fully linked; added a "run it live" section; changelog
  finalized and tagged v1.0.0.

## [ch18] - Design and tradeoffs

### Added

- `chapters/18-design-and-tradeoffs`: a written comparison to db-sync and Dolos,
  the on-chain vs ledger-state boundary, the shortcuts taken, the four design
  seams, and finality.

## [ch17] - A real cluster and forced reorgs

### Added

- `tests/test_reorg_integration.py`: forces a real node-issued rollback via
  chain-sync re-intersection and verifies the indexer rewinds and re-indexes to
  a byte-identical tip.

## [ch16] - Live view and analytics

### Added

- `chainidx.event`: an `EventBus` and `describe_block` (the event seam); the
  follower publishes forward events and rollback retractions.
- `chainidx.live`: a `/stream` WebSocket and a `/live` dashboard page with stat
  tiles, a tx-volume sparkline, and reorg highlighting.

## [ch15] - The explorer

### Added

- `web/index.html`: a single-page, vanilla-JS block explorer over the REST API.
- `chainidx.explorer.create_explorer_app`: the API plus the page at `/`;
  `make explorer` serves it.

## [ch14] - The CLI

### Added

- `chainidx.cli`: a click-based command-line interface (tip, block, tx, balance,
  pools, account, governance, and a live `follow` command).

## [ch13] - The query API

### Added

- `chainidx.api.create_app`: a Blockfrost-shaped REST API (blocks, txs,
  addresses, assets, pools, accounts, governance) over the store.
- Store query methods: `latest_blocks`, `get_tx`, `assets`; `TxDetail` model.

## [ch12] - Ouroboros wire II (chain-sync)

### Added

- `chainidx.chainsync`: the pure chain-sync message layer (find-intersect,
  request-next, and reply parsing into roll-forward/roll-backward events).
- `chainidx.node.NodeSource`: a from-scratch `ChainSource` that follows the node
  directly, replacing Ogmios behind the same interface.
- An integration test that follows a real chain via our own protocol.

## [ch11] - Ouroboros wire I (mux and handshake)

### Added

- `chainidx.mux`: mux header pack/unpack and a reassembling `MuxConnection`.
- `chainidx.handshake`: version negotiation (`propose_message`, `parse_reply`,
  `negotiate`), confirmed against a live node.
- An integration test that handshakes with a real node socket.

## [ch10] - CBOR and real blocks

### Added

- `chainidx.cbor_blocks.decode_block`: decode real Cardano blocks from raw CBOR,
  computing byte-exact block hashes and transaction ids.
- Real captured node blocks as fixtures (`tests/fixtures/node_block_*.cbor`).

## [ch09] - The sync loop

### Added

- `chainidx.follow.Follower`: resume via intersection, then loop applying
  roll-forward (index) and roll-backward (reorg) events, keeping stats.
- `Store.recent_points` for resuming; `make run` entry point.
- An integration test that follows a real chain via Ogmios into a SQLite store.

## [ch08] - A source and the Ogmios client

### Added

- `chainidx.source`: `RollForward`/`RollBackward` events, the `ChainSource`
  interface, an `Origin` marker, and a scripted `FakeSource`.
- `chainidx.ogmios_parse` (pure, covered) and `chainidx.ogmios.OgmiosSource`
  (integration-only), with real captured fixtures under `tests/fixtures/`.
- An integration test that follows a real chain from the origin via Ogmios.

## [ch07] - Conway governance

### Added

- Governance model: `DRepRegistration`, `DRepDeregistration`,
  `GovActionProposal`, `GovVote`, plus `Tx.proposals` and `Tx.votes`.
- `GovIndexer` and DRep handling in `CertIndexer`; migration 4 (governance
  tables), wired into the rollback loop.
- Derived views: `dreps`, `governance_actions`, `vote_tally`.

## [ch06] - Shelley staking

### Added

- Certificate model (`StakeRegistration`, `StakeDeregistration`,
  `StakeDelegation`, `PoolRegistration`, `PoolRetirement`) and `Tx.certificates`.
- `CertIndexer` and schema migration 3 (staking + pool tables), added to the
  generic rollback loop via `_ROLLBACK_TABLES`.
- Derived views: `pools`, `delegation_of`, `is_stake_registered`.

## [ch05] - Rollbacks and reorgs

### Added

- `SqliteStore.rollback_to(point)`: the reorg engine. Restores outputs the
  removed blocks spent, then deletes their rows leaf-first, in one transaction.
- A property test proving a reorg leaves the database identical to one built
  only from the winning branch.

## [ch04] - Indexing transactions

### Added

- `chainidx.indexers`: the pluggable indexer pipeline with `OutputIndexer` and
  `InputIndexer`.
- Schema migration 2: `tx_out`, `ma_tx_out`, `tx_in`, all block-keyed; spend
  tracking via `consumed_by_tx_id`.
- `SqliteStore.balance` and `SqliteStore.utxos` derived views.

## [ch03] - SQLite schema and store

### Added

- `chainidx.store`: a `Store` protocol and a `SqliteStore` backed by SQLite.
- A versioned migration runner and the first schema (`block`, `tx`), modelled on
  cardano-db-sync, with block-keyed rows and enforced foreign keys.

## [ch02] - The fork problem

### Added

- `chainidx.chain.Chain`: an in-memory chain with `add_block`, `has_point`,
  `find_intersection`, `rollback_to`, and `points`.
- `ForkError`, raised when a block does not build on the current tip.

## [ch01] - The block and chain model

### Added

- `chainidx.model`: immutable dataclasses `Asset`, `TxOut`, `TxIn`, `Tx`,
  `Block`, `Point`, and `Tip` that describe a Cardano chain.
- `Block.point` and `Block.links_onto`, the seed of fork detection.

## [ch00] - Orientation

### Added

- Project scaffold: `src/chainidx/` package, `tests/`, and `chapters/`.
- Tooling: ruff (lint and format), mypy (strict), pytest with a 100 percent
  coverage gate, pre-commit hooks, and a GitHub Actions CI workflow.
- Makefile with `install`, `fmt`, `lint`, `type`, `test`, and `check` targets.
- MIT license, README with the course outline, this changelog, and a progress
  checklist.
- A smoke test proving the package imports and the toolchain is wired up.
