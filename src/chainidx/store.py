"""The store: where indexed chain data lives.

We define storage as an *interface* (a ``Protocol``) and give one concrete
implementation backed by SQLite. The rest of the code depends only on the
interface, so a different backend (Postgres, for scale) could be dropped in later
without touching the indexer or the API. That is the third of the project's
design seams.

The schema is a deliberately small version of cardano-db-sync's. This chapter
creates just two tables, `block` and `tx`; later chapters add outputs, inputs,
assets, staking, and governance. Two design choices carry through all of them:

- **Every table hangs off a block.** `tx.block_id` points at `block.id`. When a
  rollback deletes a block (chapter 05), everything that belongs to it can be
  found and deleted too. New tables just need a `block_id` to roll back for free.
- **Migrations are versioned.** The schema is built by a numbered list of
  migrations. On startup we apply only the ones newer than what the database
  already has, so opening an existing database is safe and idempotent. This
  mirrors how db-sync manages its own schema.

We store hashes as hex text and amounts as integers to keep the teaching code
readable. Real db-sync uses raw `bytea` for hashes and `numeric` for lovelace so
that large sums cannot overflow; chapter 18 discusses the difference.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Any, Protocol

from chainidx.cbor_blocks import decode_cip68_datum, reference_asset_name
from chainidx.indexers import Indexer, default_indexers
from chainidx.model import (
    AccountState,
    AddressBalance,
    Asset,
    AssetDetail,
    Block,
    CertificateRecord,
    CommitteeMember,
    DRepSummary,
    DRepVote,
    EpochStats,
    EpochSummary,
    GovActionProposal,
    GovActionSummary,
    GovVoteRecord,
    MatchRecord,
    MintRecord,
    Point,
    PolicyDetail,
    PoolSummary,
    ResolvedInput,
    StakeAccountBalance,
    Tip,
    Tx,
    TxActivity,
    TxDetail,
    TxOut,
    TxSummary,
    WithdrawalRecord,
)
from chainidx.patterns import Pattern


class Store(Protocol):
    """The contract every storage backend must satisfy."""

    def apply_block(self, block: Block) -> None:
        """Persist a block and its transactions."""
        ...

    def get_block(self, block_hash: str) -> Block | None:
        """Return the stored block with this hash, or ``None``."""
        ...

    def get_block_by_number(self, block_no: int) -> Block | None:
        """Return the stored block at this height, or ``None``."""
        ...

    def get_block_by_slot(self, slot_no: int) -> Block | None:
        """Return the stored block at this slot, or ``None``."""
        ...

    def tip(self) -> Tip | None:
        """Return the newest stored block as a tip, or ``None`` if empty."""
        ...

    def block_count(self) -> int:
        """Return how many blocks are stored."""
        ...

    def total_transactions(self) -> int:
        """Return the total number of transactions across all blocks."""
        ...

    def balance(self, address: str) -> int:
        """Return the unspent lovelace held by an address."""
        ...

    def utxos(self, address: str) -> tuple[TxOut, ...]:
        """Return an address's unspent outputs."""
        ...

    def matches(self, pattern: Pattern, spent: str = "unspent") -> tuple[MatchRecord, ...]:
        """Return outputs matching a watch pattern (kupo-style, chapter 64)."""
        ...

    def get_datum(self, datum_hash: str) -> str | None:
        """Return the datum bytes (hex) for a hash we have seen inline, or ``None``."""
        ...

    def rollback_to(self, point: Point | None) -> list[str]:
        """Undo every block after ``point``; return removed hashes, newest-first."""
        ...

    def recent_points(self, limit: int = 10) -> list[Point]:
        """Return the newest stored points, newest first, for resuming."""
        ...

    def latest_blocks(self, limit: int = 20) -> list[Block]:
        """Return the most recently stored blocks, newest first."""
        ...

    def epoch_summaries(self, epoch_length: int) -> list[EpochSummary]:
        """Return per-epoch block/tx aggregates, newest epoch first."""
        ...

    def epoch_summary(self, epoch_no: int, epoch_length: int) -> EpochSummary | None:
        """Return the aggregate for one epoch, or ``None`` if it has no blocks."""
        ...

    def epoch_stats(self, epoch_length: int, limit: int = 60) -> list[EpochStats]:
        """Return per-epoch block/tx/fee totals for analytics, newest epoch first."""
        ...

    def get_tx(self, tx_hash: str) -> TxDetail | None:
        """Return a transaction's block, inputs, and outputs, or ``None``."""
        ...

    def recent_transactions(self, limit: int = 20) -> list[TxSummary]:
        """Return the most recent transactions, newest first."""
        ...

    def tx_activity(self, tx_hash: str) -> TxActivity:
        """Return a transaction's certificates and governance, as descriptions."""
        ...

    def certificates_for_tx(self, tx_hash: str) -> list[CertificateRecord]:
        """Return the certificates carried by a transaction, as typed records."""
        ...

    def proposals_for_tx(self, tx_hash: str) -> list[GovActionProposal]:
        """Return the governance actions proposed by a transaction."""
        ...

    def votes_for_tx(self, tx_hash: str) -> list[GovVoteRecord]:
        """Return the votes a transaction cast, each with the action id."""
        ...

    def withdrawals(self, limit: int = 200) -> list[WithdrawalRecord]:
        """Return recorded reward withdrawals, newest first."""
        ...

    def withdrawals_for_tx(self, tx_hash: str) -> list[WithdrawalRecord]:
        """Return the reward withdrawals made by a transaction."""
        ...

    def assets(self) -> tuple[Asset, ...]:
        """Return the native assets currently held in unspent outputs."""
        ...

    def asset_detail(self, policy_id: str, asset_name: str) -> AssetDetail | None:
        """Return one asset's total held quantity and holder count, or ``None``."""
        ...

    def policy_detail(self, policy_id: str) -> PolicyDetail | None:
        """Return the assets minted under a policy id, or ``None`` if there are none."""
        ...

    def asset_metadata(self, policy_id: str, asset_name: str) -> str | None:
        """Return an asset's CIP-25 metadata as a JSON string, or ``None``."""
        ...

    def recent_mints(self, limit: int = 50) -> list[MintRecord]:
        """Return recent mint/burn events, newest first."""
        ...

    def cip68_metadata(self, policy_id: str, asset_name: str) -> dict[str, Any] | None:
        """Return a CIP-68 token's metadata from its reference token's datum."""
        ...

    def pools(self) -> tuple[str, ...]:
        """Return the pool ids that are registered and not retired."""
        ...

    def pool_summaries(self) -> list[PoolSummary]:
        """Return a summary of each active pool (blocks, delegators, params)."""
        ...

    def pool_detail(self, pool_id: str) -> PoolSummary | None:
        """Return one active pool's summary, or ``None`` if not active."""
        ...

    def recent_blocks_by_pool(self, pool_id: str, limit: int = 20) -> list[str]:
        """Return recent block hashes minted by a pool, newest first."""
        ...

    def pool_blocks_by_epoch(self, pool_id: str, epoch_length: int) -> list[tuple[int, int]]:
        """Return ``(epoch_no, block_count)`` for a pool's blocks, oldest first."""
        ...

    def pool_delegators(self, pool_id: str, limit: int = 50) -> list[str]:
        """Return stake credentials whose latest delegation is to this pool."""
        ...

    def record_stake_distribution(self, stakes: dict[str, float], n_opt: int) -> None:
        """Replace the live-stake snapshot (from local-state-query)."""
        ...

    def record_stake_history(self, epoch: int, stakes: dict[str, float]) -> None:
        """Record each pool's live stake for an epoch (accumulating history)."""
        ...

    def pool_stake_history(self, pool_id: str) -> list[tuple[int, float]]:
        """Return ``(epoch, stake)`` for a pool over the recorded epochs, oldest first."""
        ...

    def record_protocol_params(self, params: dict[str, int]) -> None:
        """Replace the stored protocol parameters (from local-state-query)."""
        ...

    def protocol_params(self) -> dict[str, int]:
        """Return the most recent protocol parameters, or an empty dict."""
        ...

    def delegation_of(self, stake_address: str) -> str | None:
        """Return the pool a stake address most recently delegated to."""
        ...

    def is_stake_registered(self, stake_address: str) -> bool:
        """Return whether a stake address is currently registered."""
        ...

    def registered_stake_credentials(self) -> list[str]:
        """Return the distinct stake credentials seen in registrations."""
        ...

    def record_account_states(self, states: list[AccountState]) -> None:
        """Replace the per-account ledger snapshot (delegation + reward)."""
        ...

    def account_state(self, stake_address: str) -> AccountState | None:
        """Return the snapshotted delegation/reward for a stake credential."""
        ...

    def controlled_stake(self, stake_credential: str) -> int:
        """Return the unspent lovelace in outputs whose stake part is this."""
        ...

    def top_addresses(self, limit: int = 20) -> list[AddressBalance]:
        """Return the addresses holding the most unspent lovelace, richest first."""
        ...

    def top_stake_accounts(self, limit: int = 20) -> list[StakeAccountBalance]:
        """Return the stake credentials controlling the most ada, largest first."""
        ...

    def dreps(self) -> tuple[str, ...]:
        """Return the DRep ids that are registered and not retired."""
        ...

    def governance_actions(self) -> tuple[str, ...]:
        """Return the ids of all proposed governance actions."""
        ...

    def vote_tally(self, gov_action_id: str) -> dict[str, int]:
        """Return a count of Yes/No/Abstain votes for a governance action."""
        ...

    def governance_action_summaries(self) -> list[GovActionSummary]:
        """Return every governance action with its Yes/No/Abstain tally."""
        ...

    def protocol_updates(self) -> list[GovActionSummary]:
        """Return the protocol-changing governance actions (param change / hard fork)."""
        ...

    def governance_action_votes(self, gov_action_id: str) -> tuple[GovVoteRecord, ...]:
        """Return the individual votes cast on a governance action."""
        ...

    def drep_summaries(self) -> list[DRepSummary]:
        """Return each active DRep with its deposit and votes-cast count."""
        ...

    def drep_votes(self, drep_id: str) -> tuple[DRepVote, ...]:
        """Return the votes a DRep cast, each with the action it refers to."""
        ...

    def committee_members(self) -> list[CommitteeMember]:
        """Return the constitutional committee members, from their certificates."""
        ...

    def committee_member(self, cold_credential: str) -> CommitteeMember | None:
        """Return one committee member by cold credential, or ``None``."""
        ...

    def blocks_in_epoch(self, epoch_no: int, epoch_length: int, limit: int = 200) -> list[Block]:
        """Return the blocks that fall in an epoch, newest first."""
        ...

    def certificates(
        self, cert_type: str | None = None, limit: int = 200
    ) -> list[CertificateRecord]:
        """Return recorded certificates, newest first, optionally by category."""
        ...

    def certificate_summary(self) -> list[tuple[str, int]]:
        """Return ``(cert_type, count)`` pairs across all recorded certificates."""
        ...

    def close(self) -> None:
        """Release the underlying resources."""
        ...


# Each migration is (version, statements). Apply the ones newer than the
# database's current version, in order. Never edit a released migration; add a
# new one. Later chapters append to this list.
MIGRATIONS: list[tuple[int, tuple[str, ...]]] = [
    (
        1,
        (
            """
            CREATE TABLE block (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                hash      TEXT    NOT NULL UNIQUE,
                slot_no   INTEGER NOT NULL,
                block_no  INTEGER NOT NULL,
                prev_hash TEXT    NOT NULL,
                tx_count  INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE tx (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                hash        TEXT    NOT NULL UNIQUE,
                block_id    INTEGER NOT NULL REFERENCES block(id),
                block_index INTEGER NOT NULL
            )
            """,
        ),
    ),
    (
        2,
        (
            # Every table carries block_id directly, so the chapter 05 rollback
            # engine can delete a block's rows with one uniform query per table.
            # `consumed_by_tx_id` is NULL until the output is spent; an address
            # balance is the sum of its outputs where it is still NULL.
            """
            CREATE TABLE tx_out (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_id             INTEGER NOT NULL REFERENCES tx(id),
                block_id          INTEGER NOT NULL REFERENCES block(id),
                index_no          INTEGER NOT NULL,
                address           TEXT    NOT NULL,
                lovelace          INTEGER NOT NULL,
                consumed_by_tx_id INTEGER REFERENCES tx(id)
            )
            """,
            """
            CREATE TABLE ma_tx_out (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_out_id  INTEGER NOT NULL REFERENCES tx_out(id),
                block_id   INTEGER NOT NULL REFERENCES block(id),
                policy_id  TEXT    NOT NULL,
                asset_name TEXT    NOT NULL,
                quantity   INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE tx_in (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_in_id     INTEGER NOT NULL REFERENCES tx(id),
                block_id     INTEGER NOT NULL REFERENCES block(id),
                tx_out_hash  TEXT    NOT NULL,
                tx_out_index INTEGER NOT NULL
            )
            """,
            "CREATE INDEX idx_tx_out_address ON tx_out (address)",
            "CREATE INDEX idx_tx_out_tx ON tx_out (tx_id, index_no)",
            "CREATE INDEX idx_ma_tx_out_parent ON ma_tx_out (tx_out_id)",
        ),
    ),
    (
        3,
        (
            # Shelley staking certificates. Each is block-keyed like everything
            # else, so the chapter 05 rollback engine handles them once their
            # names are added to its delete loop. We store the stake address as
            # text on each row; real db-sync normalises it into a `stake_address`
            # table that it never deletes on rollback (see chapter 18).
            """
            CREATE TABLE stake_registration (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id INTEGER NOT NULL REFERENCES block(id),
                tx_id    INTEGER NOT NULL REFERENCES tx(id),
                addr     TEXT    NOT NULL
            )
            """,
            """
            CREATE TABLE stake_deregistration (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id INTEGER NOT NULL REFERENCES block(id),
                tx_id    INTEGER NOT NULL REFERENCES tx(id),
                addr     TEXT    NOT NULL
            )
            """,
            """
            CREATE TABLE delegation (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id INTEGER NOT NULL REFERENCES block(id),
                tx_id    INTEGER NOT NULL REFERENCES tx(id),
                addr     TEXT    NOT NULL,
                pool_id  TEXT    NOT NULL
            )
            """,
            """
            CREATE TABLE pool_registration (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id    INTEGER NOT NULL REFERENCES block(id),
                tx_id       INTEGER NOT NULL REFERENCES tx(id),
                pool_id     TEXT    NOT NULL,
                pledge      INTEGER NOT NULL,
                margin      REAL    NOT NULL,
                reward_addr TEXT    NOT NULL
            )
            """,
            """
            CREATE TABLE pool_retirement (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id       INTEGER NOT NULL REFERENCES block(id),
                tx_id          INTEGER NOT NULL REFERENCES tx(id),
                pool_id        TEXT    NOT NULL,
                retiring_epoch INTEGER NOT NULL
            )
            """,
            "CREATE INDEX idx_delegation_addr ON delegation (addr)",
        ),
    ),
    (
        4,
        (
            # Conway governance: DRep certificates, action proposals, and votes.
            # Block-keyed like everything else.
            """
            CREATE TABLE drep_registration (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id INTEGER NOT NULL REFERENCES block(id),
                tx_id    INTEGER NOT NULL REFERENCES tx(id),
                drep_id  TEXT    NOT NULL,
                deposit  INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE drep_deregistration (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id INTEGER NOT NULL REFERENCES block(id),
                tx_id    INTEGER NOT NULL REFERENCES tx(id),
                drep_id  TEXT    NOT NULL
            )
            """,
            """
            CREATE TABLE gov_action_proposal (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id      INTEGER NOT NULL REFERENCES block(id),
                tx_id         INTEGER NOT NULL REFERENCES tx(id),
                gov_action_id TEXT    NOT NULL,
                action_type   TEXT    NOT NULL,
                deposit       INTEGER NOT NULL,
                return_addr   TEXT    NOT NULL
            )
            """,
            """
            CREATE TABLE voting_procedure (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                block_id      INTEGER NOT NULL REFERENCES block(id),
                tx_id         INTEGER NOT NULL REFERENCES tx(id),
                gov_action_id TEXT    NOT NULL,
                voter_role    TEXT    NOT NULL,
                voter_id      TEXT    NOT NULL,
                vote          TEXT    NOT NULL
            )
            """,
            "CREATE INDEX idx_vote_action ON voting_procedure (gov_action_id)",
        ),
    ),
    (
        5,
        (
            # Which pool minted each block (chapter 22). Existing rows default to
            # '' (unknown); new blocks record the issuer pool id.
            "ALTER TABLE block ADD COLUMN issuer TEXT NOT NULL DEFAULT ''",
            "CREATE INDEX idx_block_issuer ON block (issuer)",
        ),
    ),
    (
        6,
        (
            # A ledger-state snapshot (chapter 24): live stake per pool, plus a
            # small key/value table for scalars like n_opt. This is NOT chain
            # data - it is refreshed from local-state-query and simply replaced,
            # so it is not block-keyed and does not roll back.
            "CREATE TABLE pool_stat (pool_id TEXT PRIMARY KEY, stake REAL NOT NULL)",
            "CREATE TABLE ledger_stat (key TEXT PRIMARY KEY, value REAL NOT NULL)",
        ),
    ),
    (
        7,
        (
            # Per-account ledger snapshot (chapter 26): delegation + reward,
            # refreshed from local-state-query. Not chain data; not block-keyed.
            "CREATE TABLE account_stat ("
            "  stake_address  TEXT PRIMARY KEY,"
            "  delegated_pool TEXT,"
            "  reward         INTEGER NOT NULL"
            ")",
        ),
    ),
    (
        8,
        (
            # The stake credential embedded in each output's base address, so we
            # can total the ada an account controls (chapter 29). Populated for
            # new outputs; older rows stay NULL.
            "ALTER TABLE tx_out ADD COLUMN stake_cred TEXT",
            "CREATE INDEX idx_tx_out_stake ON tx_out (stake_cred)",
        ),
    ),
    (
        9,
        (
            # A flat record of every certificate, for the Certificates browser
            # (chapter 34). The typed tables above still back the pool/DRep/account
            # queries; this one exists so every certificate kind is browsable in
            # one place, keyed by a human category label.
            "CREATE TABLE certificate ("
            "  id        INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  block_id  INTEGER NOT NULL REFERENCES block(id),"
            "  tx_id     INTEGER NOT NULL REFERENCES tx(id),"
            "  cert_type TEXT    NOT NULL,"
            "  subject   TEXT    NOT NULL,"
            "  detail    TEXT    NOT NULL"
            ")",
            "CREATE INDEX idx_certificate_type ON certificate (cert_type)",
        ),
    ),
    (
        10,
        (
            # A transaction's fee and metadata, for the detail page (chapter 35).
            # Both default for rows written before this migration.
            "ALTER TABLE tx ADD COLUMN fee INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE tx ADD COLUMN metadata TEXT NOT NULL DEFAULT ''",
        ),
    ),
    (
        11,
        (
            # The current protocol parameters, refreshed from local-state-query
            # (chapter 37). Ledger state, not chain data, so it is not block-keyed
            # and does not roll back - the next snapshot simply replaces it.
            "CREATE TABLE protocol_param (key TEXT PRIMARY KEY, value INTEGER NOT NULL)",
        ),
    ),
    (
        12,
        (
            # Reward withdrawals (chapter 39): block-keyed, so they roll back with
            # their block like every other indexed row.
            "CREATE TABLE withdrawal ("
            "  id            INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  block_id      INTEGER NOT NULL REFERENCES block(id),"
            "  tx_id         INTEGER NOT NULL REFERENCES tx(id),"
            "  stake_address TEXT    NOT NULL,"
            "  amount        INTEGER NOT NULL"
            ")",
            "CREATE INDEX idx_withdrawal_stake ON withdrawal (stake_address)",
        ),
    ),
    (
        13,
        (
            # CIP-25 asset metadata, parsed from a mint transaction's metadata
            # (label 721) and keyed by asset (chapter 46). Block-keyed, so it rolls
            # back with the mint like everything else.
            "CREATE TABLE asset_metadata ("
            "  id         INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  block_id   INTEGER NOT NULL REFERENCES block(id),"
            "  tx_id      INTEGER NOT NULL REFERENCES tx(id),"
            "  policy_id  TEXT    NOT NULL,"
            "  asset_name TEXT    NOT NULL,"
            "  metadata   TEXT    NOT NULL"
            ")",
            "CREATE INDEX idx_asset_metadata ON asset_metadata (policy_id, asset_name)",
        ),
    ),
    (
        14,
        (
            # An output's inline datum (chapter 47), where CIP-68 metadata lives.
            # It hangs off tx_out, so it rolls back with the output.
            "ALTER TABLE tx_out ADD COLUMN datum TEXT NOT NULL DEFAULT ''",
        ),
    ),
    (
        15,
        (
            # A pool's fixed cost and off-chain metadata anchor (chapter 48).
            "ALTER TABLE pool_registration ADD COLUMN cost INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE pool_registration ADD COLUMN metadata_url TEXT NOT NULL DEFAULT ''",
        ),
    ),
    (
        16,
        (
            # Mint/burn events (chapter 49), from a transaction's mint field.
            # Block-keyed, so they roll back with their block.
            "CREATE TABLE mint_event ("
            "  id         INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  block_id   INTEGER NOT NULL REFERENCES block(id),"
            "  tx_id      INTEGER NOT NULL REFERENCES tx(id),"
            "  policy_id  TEXT    NOT NULL,"
            "  asset_name TEXT    NOT NULL,"
            "  quantity   INTEGER NOT NULL"
            ")",
        ),
    ),
    (
        17,
        (
            # The rest of a pool's on-chain registration details (chapter 50):
            # VRF key hash, metadata hash, and JSON arrays of owners and relays.
            "ALTER TABLE pool_registration ADD COLUMN vrf_hash TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE pool_registration ADD COLUMN metadata_hash TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE pool_registration ADD COLUMN owners TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE pool_registration ADD COLUMN relays TEXT NOT NULL DEFAULT '[]'",
        ),
    ),
    (
        18,
        (
            # Per-epoch live-stake history (chapter 55), accumulated from
            # local-state-query snapshots. Ledger state, not chain data, so it is
            # not block-keyed and does not roll back; one row per (epoch, pool).
            "CREATE TABLE stake_history ("
            "  epoch   INTEGER NOT NULL,"
            "  pool_id TEXT    NOT NULL,"
            "  stake   REAL    NOT NULL,"
            "  PRIMARY KEY (epoch, pool_id)"
            ")",
        ),
    ),
    (
        19,
        (
            # An output's datum hash (chapter 67), for kupo-style datum lookup. For
            # an inline datum it is the blake2b-256 of the datum bytes we already
            # keep; for a by-reference datum it is the hash the output carried.
            "ALTER TABLE tx_out ADD COLUMN datum_hash TEXT NOT NULL DEFAULT ''",
            "CREATE INDEX idx_tx_out_datum_hash ON tx_out (datum_hash)",
        ),
    ),
]

# Leaf tables (everything that references tx or block) are deleted before tx and
# block during a rollback. Each new indexer chapter appends its tables here.
_ROLLBACK_TABLES: tuple[str, ...] = (
    "ma_tx_out",
    "tx_out",
    "tx_in",
    "stake_registration",
    "stake_deregistration",
    "delegation",
    "pool_registration",
    "pool_retirement",
    "drep_registration",
    "drep_deregistration",
    "certificate",
    "withdrawal",
    "asset_metadata",
    "mint_event",
    "gov_action_proposal",
    "voting_procedure",
    "tx",
)


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Bring the database schema up to the newest migration version."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current: int = row[0] if row is not None and row[0] is not None else 0

    for version, statements in MIGRATIONS:
        if version > current:
            for sql in statements:
                conn.execute(sql)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()


class SqliteStore:
    """A store backed by SQLite. Satisfies the ``Store`` protocol."""

    def __init__(self, path: str = ":memory:", indexers: Sequence[Indexer] | None = None) -> None:
        # check_same_thread=False lets the read-only API serve queries from
        # FastAPI's worker threads. SQLite serializes access internally; the
        # follower is the only writer, so this is safe for our use.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Enforce foreign keys so a bad delete order is caught, not silently
        # allowed. Chapter 05 relies on this to prove leaf-first deletion.
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._indexers: tuple[Indexer, ...] = (
            tuple(indexers) if indexers is not None else default_indexers()
        )
        _run_migrations(self._conn)

    def apply_block(self, block: Block) -> None:
        # `with self._conn` opens a transaction that commits on success and
        # rolls back if anything raises - so a half-written block never lands.
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO block (hash, slot_no, block_no, prev_hash, tx_count, issuer) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    block.block_hash,
                    block.slot_no,
                    block.block_no,
                    block.prev_hash,
                    len(block.txs),
                    block.issuer,
                ),
            )
            block_id = cur.lastrowid
            assert block_id is not None
            for index, tx in enumerate(block.txs):
                cur = self._conn.execute(
                    "INSERT INTO tx (hash, block_id, block_index, fee, metadata) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (tx.tx_id, block_id, index, tx.fee, tx.metadata),
                )
                tx_db_id = cur.lastrowid
                assert tx_db_id is not None
                for indexer in self._indexers:
                    indexer.index_tx(self._conn, block_id, tx_db_id, tx)

    def get_block(self, block_hash: str) -> Block | None:
        row = self._conn.execute(
            "SELECT id, hash, slot_no, block_no, prev_hash, issuer FROM block WHERE hash = ?",
            (block_hash,),
        ).fetchone()
        if row is None:
            return None
        tx_rows = self._conn.execute(
            "SELECT hash FROM tx WHERE block_id = ? ORDER BY block_index",
            (row["id"],),
        ).fetchall()
        txs = tuple(Tx(tx_id=r["hash"]) for r in tx_rows)
        return Block(
            block_no=row["block_no"],
            slot_no=row["slot_no"],
            block_hash=row["hash"],
            prev_hash=row["prev_hash"],
            txs=txs,
            issuer=row["issuer"],
        )

    def get_block_by_number(self, block_no: int) -> Block | None:
        row = self._conn.execute(
            "SELECT hash FROM block WHERE block_no = ? LIMIT 1", (block_no,)
        ).fetchone()
        return None if row is None else self.get_block(row["hash"])

    def get_block_by_slot(self, slot_no: int) -> Block | None:
        row = self._conn.execute(
            "SELECT hash FROM block WHERE slot_no = ? LIMIT 1", (slot_no,)
        ).fetchone()
        return None if row is None else self.get_block(row["hash"])

    def tip(self) -> Tip | None:
        row = self._conn.execute(
            "SELECT hash, slot_no, block_no FROM block ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Tip(
            point=Point(slot_no=row["slot_no"], block_hash=row["hash"]),
            block_no=row["block_no"],
        )

    def block_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM block").fetchone()
        return int(row["n"])

    def total_transactions(self) -> int:
        row = self._conn.execute("SELECT COALESCE(SUM(tx_count), 0) AS n FROM block").fetchone()
        return int(row["n"])

    def balance(self, address: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(lovelace), 0) AS bal FROM tx_out "
            "WHERE address = ? AND consumed_by_tx_id IS NULL",
            (address,),
        ).fetchone()
        return int(row["bal"])

    def utxos(self, address: str) -> tuple[TxOut, ...]:
        rows = self._conn.execute(
            "SELECT id, address, lovelace, datum_hash FROM tx_out "
            "WHERE address = ? AND consumed_by_tx_id IS NULL ORDER BY id",
            (address,),
        ).fetchall()
        outputs: list[TxOut] = []
        for r in rows:
            asset_rows = self._conn.execute(
                "SELECT policy_id, asset_name, quantity FROM ma_tx_out "
                "WHERE tx_out_id = ? ORDER BY id",
                (r["id"],),
            ).fetchall()
            assets = tuple(
                Asset(policy_id=a["policy_id"], asset_name=a["asset_name"], quantity=a["quantity"])
                for a in asset_rows
            )
            outputs.append(
                TxOut(
                    address=r["address"],
                    lovelace=r["lovelace"],
                    assets=assets,
                    datum_hash=r["datum_hash"] or "",
                )
            )
        return tuple(outputs)

    def matches(self, pattern: Pattern, spent: str = "unspent") -> tuple[MatchRecord, ...]:
        """Return the outputs matching a watch pattern (kupo-style, chapter 64).

        This is a query over the index we already keep: ``tx_out`` (address, value,
        datum, and ``consumed_by_tx_id`` for spent-ness) joined to ``ma_tx_out`` for
        the policy/asset patterns. ``spent`` is ``"unspent"`` (the default, kupo's
        common case), ``"spent"``, or ``"all"``. The output reference is the
        transaction hash and output index, as kupo returns it.

        The ``WHERE`` fragments below are fixed strings chosen by the pattern kind;
        every value the caller supplies is passed as a bound parameter.
        """
        where = ["1 = 1"]
        params: list[object] = []
        join = ""
        if pattern.kind == "address":
            where.append("o.address = ?")
            params.append(pattern.value)
        elif pattern.kind == "stake":
            where.append("o.stake_cred = ?")
            params.append(pattern.value)
        elif pattern.kind == "policy":
            join = "JOIN ma_tx_out m ON m.tx_out_id = o.id"
            where.append("m.policy_id = ?")
            params.append(pattern.value)
        elif pattern.kind == "asset":
            join = "JOIN ma_tx_out m ON m.tx_out_id = o.id"
            where.append("m.policy_id = ? AND m.asset_name = ?")
            params.extend((pattern.value, pattern.asset_name))
        elif pattern.kind != "all":
            return ()
        if spent == "unspent":
            where.append("o.consumed_by_tx_id IS NULL")
        elif spent == "spent":
            where.append("o.consumed_by_tx_id IS NOT NULL")
        rows = self._conn.execute(
            "SELECT DISTINCT o.id AS id, o.index_no AS index_no, o.address AS address, "
            "o.lovelace AS lovelace, o.datum AS datum, o.datum_hash AS datum_hash, "
            "t.hash AS tx_hash, o.consumed_by_tx_id AS spent_id "
            f"FROM tx_out o JOIN tx t ON t.id = o.tx_id {join} "
            f"WHERE {' AND '.join(where)} ORDER BY o.id",
            tuple(params),
        ).fetchall()
        records: list[MatchRecord] = []
        for r in rows:
            asset_rows = self._conn.execute(
                "SELECT policy_id, asset_name, quantity FROM ma_tx_out "
                "WHERE tx_out_id = ? ORDER BY id",
                (r["id"],),
            ).fetchall()
            assets = tuple(
                Asset(policy_id=a["policy_id"], asset_name=a["asset_name"], quantity=a["quantity"])
                for a in asset_rows
            )
            records.append(
                MatchRecord(
                    tx_hash=r["tx_hash"],
                    output_index=r["index_no"],
                    address=r["address"],
                    lovelace=int(r["lovelace"]),
                    assets=assets,
                    datum=r["datum"] or "",
                    datum_hash=r["datum_hash"] or "",
                    spent=r["spent_id"] is not None,
                )
            )
        return tuple(records)

    def get_datum(self, datum_hash: str) -> str | None:
        """Return the inline-datum bytes (hex) with this hash, if we have seen one.

        We only have a preimage for datums that appeared inline in an output; a
        by-reference datum hash with no inline sighting returns ``None``.
        """
        row = self._conn.execute(
            "SELECT datum FROM tx_out WHERE datum_hash = ? AND datum != '' LIMIT 1",
            (datum_hash,),
        ).fetchone()
        return str(row["datum"]) if row is not None else None

    def rollback_to(self, point: Point | None) -> list[str]:
        """Undo every block after ``point`` and return the removed hashes.

        This is the reorg engine. ``point`` is where the node told us to back up
        to (or ``None`` for the origin, meaning "throw everything away"). We map
        the point to a block id and then undo everything above it.

        The order below is not arbitrary; foreign keys force it:

        1. **Un-consume first.** Outputs from *surviving* blocks may have been
           spent by transactions in the blocks we are about to delete. We clear
           their `consumed_by_tx_id` so those outputs become unspent again -
           this is how a rollback restores balances. It must happen before we
           delete those transactions, or the foreign key would refuse.
        2. **Delete leaf-first.** `ma_tx_out` before `tx_out` (it points at it),
           and everything that points at `tx` before `tx`, and `tx` before
           `block`. Deleting a parent before its children would raise a foreign
           key error - which is exactly the safety net we want.

        Everything runs in one transaction, so a crash mid-rollback leaves the
        database untouched rather than half-rewound.
        """
        if point is None:
            target_id = 0
        else:
            row = self._conn.execute(
                "SELECT id FROM block WHERE hash = ?", (point.block_hash,)
            ).fetchone()
            if row is None:
                raise ValueError(f"cannot roll back to unknown point: {point!r}")
            target_id = int(row["id"])

        removed = [
            r["hash"]
            for r in self._conn.execute(
                "SELECT hash FROM block WHERE id > ? ORDER BY id DESC", (target_id,)
            ).fetchall()
        ]

        with self._conn:
            # 1. Restore outputs that the removed transactions had consumed.
            self._conn.execute(
                "UPDATE tx_out SET consumed_by_tx_id = NULL "
                "WHERE consumed_by_tx_id IN (SELECT id FROM tx WHERE block_id > ?)",
                (target_id,),
            )
            # 2. Delete the removed blocks' rows, leaf-first.
            for table in _ROLLBACK_TABLES:
                self._conn.execute(f"DELETE FROM {table} WHERE block_id > ?", (target_id,))
            self._conn.execute("DELETE FROM block WHERE id > ?", (target_id,))

        return removed

    def recent_points(self, limit: int = 10) -> list[Point]:
        rows = self._conn.execute(
            "SELECT hash, slot_no FROM block ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Point(slot_no=r["slot_no"], block_hash=r["hash"]) for r in rows]

    def latest_blocks(self, limit: int = 20) -> list[Block]:
        rows = self._conn.execute(
            "SELECT hash FROM block ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        blocks = [self.get_block(r["hash"]) for r in rows]
        return [b for b in blocks if b is not None]

    def epoch_summaries(self, epoch_length: int) -> list[EpochSummary]:
        # Epoch = slot_no // epoch_length. We group the blocks by that integer
        # division, so no epoch column is needed on the row.
        rows = self._conn.execute(
            "SELECT slot_no / ? AS epoch_no, COUNT(*) AS blocks, "
            "COALESCE(SUM(tx_count), 0) AS txs, MIN(slot_no) AS start_slot, "
            "MAX(slot_no) AS end_slot FROM block GROUP BY epoch_no ORDER BY epoch_no DESC",
            (epoch_length,),
        ).fetchall()
        return [
            EpochSummary(
                epoch_no=r["epoch_no"],
                block_count=r["blocks"],
                tx_count=r["txs"],
                start_slot=r["start_slot"],
                end_slot=r["end_slot"],
            )
            for r in rows
        ]

    def epoch_summary(self, epoch_no: int, epoch_length: int) -> EpochSummary | None:
        row = self._conn.execute(
            "SELECT COUNT(*) AS blocks, COALESCE(SUM(tx_count), 0) AS txs, "
            "MIN(slot_no) AS start_slot, MAX(slot_no) AS end_slot FROM block "
            "WHERE slot_no / ? = ?",
            (epoch_length, epoch_no),
        ).fetchone()
        if row is None or row["blocks"] == 0:
            return None
        return EpochSummary(
            epoch_no=epoch_no,
            block_count=row["blocks"],
            tx_count=row["txs"],
            start_slot=row["start_slot"],
            end_slot=row["end_slot"],
        )

    def epoch_stats(self, epoch_length: int, limit: int = 60) -> list[EpochStats]:
        # Left-join tx to block so empty epochs still count their blocks; a
        # DISTINCT block count avoids the join inflating it, and the fee sum comes
        # from the tx rows.
        rows = self._conn.execute(
            "SELECT b.slot_no / ? AS epoch_no, COUNT(DISTINCT b.id) AS blocks, "
            "COUNT(t.id) AS txs, COALESCE(SUM(t.fee), 0) AS fees "
            "FROM block b LEFT JOIN tx t ON t.block_id = b.id "
            "GROUP BY epoch_no ORDER BY epoch_no DESC LIMIT ?",
            (epoch_length, limit),
        ).fetchall()
        return [
            EpochStats(
                epoch_no=r["epoch_no"],
                block_count=r["blocks"],
                tx_count=r["txs"],
                fee_total=int(r["fees"]),
            )
            for r in rows
        ]

    def _assets_of_output(self, tx_out_id: int) -> tuple[Asset, ...]:
        rows = self._conn.execute(
            "SELECT policy_id, asset_name, quantity FROM ma_tx_out WHERE tx_out_id = ?",
            (tx_out_id,),
        ).fetchall()
        return tuple(
            Asset(policy_id=r["policy_id"], asset_name=r["asset_name"], quantity=r["quantity"])
            for r in rows
        )

    def recent_transactions(self, limit: int = 20) -> list[TxSummary]:
        rows = self._conn.execute(
            "SELECT t.hash AS tx_hash, t.fee AS fee, b.hash AS block_hash, "
            "b.block_no AS block_no, b.slot_no AS slot_no, COUNT(o.id) AS out_count, "
            "COALESCE(SUM(o.lovelace), 0) AS out_total "
            "FROM tx t JOIN block b ON b.id = t.block_id "
            "LEFT JOIN tx_out o ON o.tx_id = t.id "
            # Group by every non-aggregated column so this is valid on Postgres
            # too (SQLite is laxer and would accept just t.id).
            "GROUP BY t.id, t.hash, t.fee, b.hash, b.block_no, b.slot_no "
            "ORDER BY t.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            TxSummary(
                tx_id=r["tx_hash"],
                block_hash=r["block_hash"],
                block_no=r["block_no"],
                slot_no=r["slot_no"],
                fee=r["fee"],
                output_count=r["out_count"],
                total_output=int(r["out_total"]),
            )
            for r in rows
        ]

    def get_tx(self, tx_hash: str) -> TxDetail | None:
        row = self._conn.execute(
            "SELECT t.id AS id, t.fee AS fee, t.metadata AS metadata, b.hash AS block_hash "
            "FROM tx t JOIN block b ON b.id = t.block_id WHERE t.hash = ?",
            (tx_hash,),
        ).fetchone()
        if row is None:
            return None
        out_rows = self._conn.execute(
            "SELECT id, address, lovelace, datum_hash FROM tx_out "
            "WHERE tx_id = ? ORDER BY index_no",
            (row["id"],),
        ).fetchall()
        outputs = tuple(
            TxOut(
                address=r["address"],
                lovelace=r["lovelace"],
                assets=self._assets_of_output(r["id"]),
                datum_hash=r["datum_hash"] or "",
            )
            for r in out_rows
        )
        in_rows = self._conn.execute(
            "SELECT tx_out_hash, tx_out_index FROM tx_in WHERE tx_in_id = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
        inputs = tuple(self._resolve_input(r["tx_out_hash"], r["tx_out_index"]) for r in in_rows)
        return TxDetail(
            tx_id=tx_hash,
            block_hash=row["block_hash"],
            inputs=inputs,
            outputs=outputs,
            fee=row["fee"],
            metadata=row["metadata"],
        )

    def _resolve_input(self, tx_out_hash: str, index: int) -> ResolvedInput:
        src = self._conn.execute(
            "SELECT o.id AS id, o.address AS address, o.lovelace AS lovelace FROM tx_out o "
            "JOIN tx t ON t.id = o.tx_id WHERE t.hash = ? AND o.index_no = ?",
            (tx_out_hash, index),
        ).fetchone()
        if src is None:
            # The consumed output was never indexed (a genesis or faucet UTxO, or
            # one from before our sync start). We know the reference but not the
            # value, and there is no transaction page to link to.
            return ResolvedInput(tx_id=tx_out_hash, index=index, address="", lovelace=0)
        return ResolvedInput(
            tx_id=tx_out_hash,
            index=index,
            address=src["address"],
            lovelace=src["lovelace"],
            assets=self._assets_of_output(src["id"]),
        )

    def certificates_for_tx(self, tx_hash: str) -> list[CertificateRecord]:
        rows = self._conn.execute(
            "SELECT c.cert_type AS cert_type, c.subject AS subject, c.detail AS detail "
            "FROM certificate c JOIN tx t ON t.id = c.tx_id WHERE t.hash = ? ORDER BY c.id",
            (tx_hash,),
        ).fetchall()
        return [
            CertificateRecord(
                cert_type=r["cert_type"],
                subject=r["subject"],
                detail=r["detail"],
                tx_hash=tx_hash,
            )
            for r in rows
        ]

    def proposals_for_tx(self, tx_hash: str) -> list[GovActionProposal]:
        rows = self._conn.execute(
            "SELECT p.gov_action_id AS gid, p.action_type AS action_type, p.deposit AS deposit, "
            "p.return_addr AS return_addr FROM gov_action_proposal p "
            "JOIN tx t ON t.id = p.tx_id WHERE t.hash = ? ORDER BY p.id",
            (tx_hash,),
        ).fetchall()
        return [
            GovActionProposal(
                gov_action_id=r["gid"],
                action_type=r["action_type"],
                deposit=r["deposit"],
                return_address=r["return_addr"],
            )
            for r in rows
        ]

    def votes_for_tx(self, tx_hash: str) -> list[GovVoteRecord]:
        rows = self._conn.execute(
            "SELECT v.gov_action_id AS gid, v.voter_role AS voter_role, v.voter_id AS voter_id, "
            "v.vote AS vote FROM voting_procedure v "
            "JOIN tx t ON t.id = v.tx_id WHERE t.hash = ? ORDER BY v.id",
            (tx_hash,),
        ).fetchall()
        return [
            GovVoteRecord(
                voter_role=r["voter_role"],
                voter_id=r["voter_id"],
                vote=r["vote"],
                gov_action_id=r["gid"],
            )
            for r in rows
        ]

    def withdrawals(self, limit: int = 200) -> list[WithdrawalRecord]:
        rows = self._conn.execute(
            "SELECT w.stake_address AS stake_address, w.amount AS amount, t.hash AS tx_hash "
            "FROM withdrawal w JOIN tx t ON t.id = w.tx_id ORDER BY w.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            WithdrawalRecord(
                stake_address=r["stake_address"], amount=r["amount"], tx_hash=r["tx_hash"]
            )
            for r in rows
        ]

    def withdrawals_for_tx(self, tx_hash: str) -> list[WithdrawalRecord]:
        rows = self._conn.execute(
            "SELECT w.stake_address AS stake_address, w.amount AS amount "
            "FROM withdrawal w JOIN tx t ON t.id = w.tx_id WHERE t.hash = ? ORDER BY w.id",
            (tx_hash,),
        ).fetchall()
        return [
            WithdrawalRecord(stake_address=r["stake_address"], amount=r["amount"], tx_hash=tx_hash)
            for r in rows
        ]

    def tx_activity(self, tx_hash: str) -> TxActivity:
        row = self._conn.execute("SELECT id FROM tx WHERE hash = ?", (tx_hash,)).fetchone()
        if row is None:
            return TxActivity(certificates=(), proposals=(), votes=())
        tx_id = row["id"]

        def q(sql: str) -> list[Any]:
            return self._conn.execute(sql, (tx_id,)).fetchall()

        certs: list[str] = []
        certs += [
            f"stake registration: {r['addr']}"
            for r in q("SELECT addr FROM stake_registration WHERE tx_id = ?")
        ]
        certs += [
            f"stake deregistration: {r['addr']}"
            for r in q("SELECT addr FROM stake_deregistration WHERE tx_id = ?")
        ]
        certs += [
            f"delegation: {r['addr']} -> {r['pool_id']}"
            for r in q("SELECT addr, pool_id FROM delegation WHERE tx_id = ?")
        ]
        certs += [
            f"pool registration: {r['pool_id']}"
            for r in q("SELECT pool_id FROM pool_registration WHERE tx_id = ?")
        ]
        certs += [
            f"pool retirement: {r['pool_id']} @ epoch {r['retiring_epoch']}"
            for r in q("SELECT pool_id, retiring_epoch FROM pool_retirement WHERE tx_id = ?")
        ]
        certs += [
            f"DRep registration: {r['drep_id']}"
            for r in q("SELECT drep_id FROM drep_registration WHERE tx_id = ?")
        ]
        certs += [
            f"DRep retirement: {r['drep_id']}"
            for r in q("SELECT drep_id FROM drep_deregistration WHERE tx_id = ?")
        ]

        proposals = [
            f"{r['action_type']}: {r['gov_action_id']}"
            for r in q("SELECT action_type, gov_action_id FROM gov_action_proposal WHERE tx_id = ?")
        ]
        votes = [
            f"{r['voter_role']} voted {r['vote']} on {r['gov_action_id']}"
            for r in q(
                "SELECT voter_role, vote, gov_action_id FROM voting_procedure WHERE tx_id = ?"
            )
        ]

        return TxActivity(certificates=tuple(certs), proposals=tuple(proposals), votes=tuple(votes))

    def assets(self) -> tuple[Asset, ...]:
        rows = self._conn.execute(
            "SELECT m.policy_id AS policy_id, m.asset_name AS asset_name, "
            "SUM(m.quantity) AS qty FROM ma_tx_out m "
            "JOIN tx_out o ON o.id = m.tx_out_id "
            "WHERE o.consumed_by_tx_id IS NULL "
            "GROUP BY m.policy_id, m.asset_name ORDER BY m.policy_id, m.asset_name"
        ).fetchall()
        return tuple(
            Asset(policy_id=r["policy_id"], asset_name=r["asset_name"], quantity=int(r["qty"]))
            for r in rows
        )

    def asset_detail(self, policy_id: str, asset_name: str) -> AssetDetail | None:
        row = self._conn.execute(
            "SELECT SUM(m.quantity) AS qty, COUNT(DISTINCT o.address) AS holders "
            "FROM ma_tx_out m JOIN tx_out o ON o.id = m.tx_out_id "
            "WHERE m.policy_id = ? AND m.asset_name = ? AND o.consumed_by_tx_id IS NULL",
            (policy_id, asset_name),
        ).fetchone()
        if row is None or row["qty"] is None:
            return None
        return AssetDetail(
            policy_id=policy_id,
            asset_name=asset_name,
            quantity=int(row["qty"]),
            holders=int(row["holders"]),
        )

    def policy_detail(self, policy_id: str) -> PolicyDetail | None:
        rows = self._conn.execute(
            "SELECT m.asset_name AS asset_name, SUM(m.quantity) AS qty, "
            "COUNT(DISTINCT o.address) AS holders FROM ma_tx_out m "
            "JOIN tx_out o ON o.id = m.tx_out_id "
            "WHERE m.policy_id = ? AND o.consumed_by_tx_id IS NULL "
            "GROUP BY m.asset_name ORDER BY m.asset_name",
            (policy_id,),
        ).fetchall()
        if not rows:
            return None
        assets = tuple(
            AssetDetail(
                policy_id=policy_id,
                asset_name=r["asset_name"],
                quantity=int(r["qty"]),
                holders=int(r["holders"]),
            )
            for r in rows
        )
        return PolicyDetail(policy_id=policy_id, asset_count=len(assets), assets=assets)

    def asset_metadata(self, policy_id: str, asset_name: str) -> str | None:
        row = self._conn.execute(
            "SELECT metadata FROM asset_metadata "
            "WHERE policy_id = ? AND asset_name = ? ORDER BY id DESC LIMIT 1",
            (policy_id, asset_name),
        ).fetchone()
        return str(row["metadata"]) if row is not None else None

    def recent_mints(self, limit: int = 50) -> list[MintRecord]:
        rows = self._conn.execute(
            "SELECT t.hash AS tx_hash, m.policy_id AS policy_id, m.asset_name AS asset_name, "
            "m.quantity AS quantity FROM mint_event m JOIN tx t ON t.id = m.tx_id "
            "ORDER BY m.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            MintRecord(
                tx_hash=r["tx_hash"],
                policy_id=r["policy_id"],
                asset_name=r["asset_name"],
                quantity=r["quantity"],
            )
            for r in rows
        ]

    def cip68_metadata(self, policy_id: str, asset_name: str) -> dict[str, Any] | None:
        # CIP-68 metadata rides on the reference token (same policy, name with the
        # (100) prefix). We find an unspent output holding it that carries an inline
        # datum, and decode that datum's metadata map.
        reference = reference_asset_name(asset_name)
        if reference is None:
            return None
        row = self._conn.execute(
            "SELECT o.datum AS datum FROM ma_tx_out m JOIN tx_out o ON o.id = m.tx_out_id "
            "WHERE m.policy_id = ? AND m.asset_name = ? AND o.consumed_by_tx_id IS NULL "
            "AND o.datum != '' ORDER BY o.id DESC LIMIT 1",
            (policy_id, reference),
        ).fetchone()
        if row is None:
            return None
        metadata = decode_cip68_datum(row["datum"])
        return metadata or None

    def pools(self) -> tuple[str, ...]:
        # A pool counts as active if it has a registration and no retirement.
        # Real retirement is scheduled for a future epoch; we simplify here and
        # revisit the nuance in chapter 18.
        rows = self._conn.execute(
            "SELECT DISTINCT pool_id FROM pool_registration "
            "WHERE pool_id NOT IN (SELECT pool_id FROM pool_retirement) "
            "ORDER BY pool_id"
        ).fetchall()
        return tuple(r["pool_id"] for r in rows)

    def record_stake_distribution(self, stakes: dict[str, float], n_opt: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM pool_stat")
            self._conn.executemany(
                "INSERT INTO pool_stat (pool_id, stake) VALUES (?, ?)", list(stakes.items())
            )
            self._conn.execute(
                "INSERT INTO ledger_stat (key, value) VALUES ('n_opt', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (float(n_opt),),
            )

    def record_stake_history(self, epoch: int, stakes: dict[str, float]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO stake_history (epoch, pool_id, stake) VALUES (?, ?, ?) "
                "ON CONFLICT(epoch, pool_id) DO UPDATE SET stake = excluded.stake",
                [(epoch, pool_id, stake) for pool_id, stake in stakes.items()],
            )

    def pool_stake_history(self, pool_id: str) -> list[tuple[int, float]]:
        rows = self._conn.execute(
            "SELECT epoch, stake FROM stake_history WHERE pool_id = ? ORDER BY epoch",
            (pool_id,),
        ).fetchall()
        return [(r["epoch"], float(r["stake"])) for r in rows]

    def record_protocol_params(self, params: dict[str, int]) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM protocol_param")
            self._conn.executemany(
                "INSERT INTO protocol_param (key, value) VALUES (?, ?)", list(params.items())
            )

    def protocol_params(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT key, value FROM protocol_param ORDER BY key").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def _ledger_stat(self, key: str) -> float:
        row = self._conn.execute("SELECT value FROM ledger_stat WHERE key = ?", (key,)).fetchone()
        return float(row["value"]) if row is not None else 0.0

    def _live_stake(self, pool_id: str) -> float:
        row = self._conn.execute(
            "SELECT stake FROM pool_stat WHERE pool_id = ?", (pool_id,)
        ).fetchone()
        return float(row["stake"]) if row is not None else 0.0

    def _pool_summary(self, pool_id: str) -> PoolSummary:
        reg = self._conn.execute(
            "SELECT pr.pledge AS pledge, pr.margin AS margin, pr.reward_addr AS reward_addr, "
            "pr.cost AS cost, pr.metadata_url AS metadata_url, pr.vrf_hash AS vrf_hash, "
            "pr.metadata_hash AS metadata_hash, pr.owners AS owners, pr.relays AS relays, "
            "b.slot_no AS reg_slot FROM pool_registration pr JOIN block b ON b.id = pr.block_id "
            "WHERE pr.pool_id = ? ORDER BY pr.tx_id DESC LIMIT 1",
            (pool_id,),
        ).fetchone()
        blocks = self._conn.execute(
            "SELECT COUNT(*) AS n FROM block WHERE issuer = ?", (pool_id,)
        ).fetchone()["n"]
        # A delegator counts if its most recent delegation (highest tx_id) is to
        # this pool.
        delegators = self._conn.execute(
            "SELECT COUNT(*) AS n FROM delegation d WHERE d.pool_id = ? "
            "AND d.tx_id = (SELECT MAX(tx_id) FROM delegation d2 WHERE d2.addr = d.addr)",
            (pool_id,),
        ).fetchone()["n"]
        live_stake = self._live_stake(pool_id)
        n_opt = self._ledger_stat("n_opt")
        # Saturation of 1.0 means the pool holds the ideal 1/n_opt share.
        saturation = live_stake * n_opt if n_opt > 0 else 0.0
        return PoolSummary(
            pool_id=pool_id,
            blocks_minted=blocks,
            delegators=delegators,
            pledge=reg["pledge"] if reg is not None else 0,
            margin=reg["margin"] if reg is not None else 0.0,
            reward_address=reg["reward_addr"] if reg is not None else "",
            live_stake=live_stake,
            saturation=saturation,
            cost=reg["cost"] if reg is not None else 0,
            metadata_url=reg["metadata_url"] if reg is not None else "",
            vrf_hash=reg["vrf_hash"] if reg is not None else "",
            metadata_hash=reg["metadata_hash"] if reg is not None else "",
            owners=tuple(json.loads(reg["owners"])) if reg is not None else (),
            relays=tuple(json.loads(reg["relays"])) if reg is not None else (),
            registered_slot=reg["reg_slot"] if reg is not None else -1,
        )

    def pool_summaries(self) -> list[PoolSummary]:
        return [self._pool_summary(pool_id) for pool_id in self.pools()]

    def pool_blocks_by_epoch(self, pool_id: str, epoch_length: int) -> list[tuple[int, int]]:
        """Return ``(epoch_no, block_count)`` for a pool's minted blocks, oldest first."""
        rows = self._conn.execute(
            "SELECT slot_no / ? AS epoch_no, COUNT(*) AS n FROM block "
            "WHERE issuer = ? GROUP BY epoch_no ORDER BY epoch_no",
            (epoch_length, pool_id),
        ).fetchall()
        return [(r["epoch_no"], r["n"]) for r in rows]

    def pool_detail(self, pool_id: str) -> PoolSummary | None:
        if pool_id not in self.pools():
            return None
        return self._pool_summary(pool_id)

    def recent_blocks_by_pool(self, pool_id: str, limit: int = 20) -> list[str]:
        rows = self._conn.execute(
            "SELECT hash FROM block WHERE issuer = ? ORDER BY id DESC LIMIT ?",
            (pool_id, limit),
        ).fetchall()
        return [r["hash"] for r in rows]

    def pool_delegators(self, pool_id: str, limit: int = 50) -> list[str]:
        rows = self._conn.execute(
            "SELECT d.addr AS addr FROM delegation d WHERE d.pool_id = ? "
            "AND d.tx_id = (SELECT MAX(tx_id) FROM delegation d2 WHERE d2.addr = d.addr) "
            "ORDER BY d.addr LIMIT ?",
            (pool_id, limit),
        ).fetchall()
        return [r["addr"] for r in rows]

    def delegation_of(self, stake_address: str) -> str | None:
        row = self._conn.execute(
            "SELECT pool_id FROM delegation WHERE addr = ? ORDER BY id DESC LIMIT 1",
            (stake_address,),
        ).fetchone()
        return None if row is None else str(row["pool_id"])

    def is_stake_registered(self, stake_address: str) -> bool:
        # Registered if its most recent registration happened after its most
        # recent deregistration. We order by tx_id, which is a global
        # autoincrement and so increases with chain order across both tables
        # (the per-table id columns are separate sequences and not comparable).
        reg = self._conn.execute(
            "SELECT MAX(tx_id) AS m FROM stake_registration WHERE addr = ?", (stake_address,)
        ).fetchone()["m"]
        if reg is None:
            return False
        dereg = self._conn.execute(
            "SELECT MAX(tx_id) AS m FROM stake_deregistration WHERE addr = ?", (stake_address,)
        ).fetchone()["m"]
        return dereg is None or reg > dereg

    def registered_stake_credentials(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT addr FROM stake_registration ORDER BY addr"
        ).fetchall()
        return [r["addr"] for r in rows]

    def record_account_states(self, states: list[AccountState]) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM account_stat")
            self._conn.executemany(
                "INSERT INTO account_stat (stake_address, delegated_pool, reward) VALUES (?, ?, ?)",
                [(s.stake_address, s.delegated_pool, s.reward) for s in states],
            )

    def account_state(self, stake_address: str) -> AccountState | None:
        row = self._conn.execute(
            "SELECT stake_address, delegated_pool, reward FROM account_stat "
            "WHERE stake_address = ?",
            (stake_address,),
        ).fetchone()
        if row is None:
            return None
        return AccountState(
            stake_address=row["stake_address"],
            delegated_pool=row["delegated_pool"],
            reward=row["reward"],
        )

    def controlled_stake(self, stake_credential: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(lovelace), 0) AS total FROM tx_out "
            "WHERE stake_cred = ? AND consumed_by_tx_id IS NULL",
            (stake_credential,),
        ).fetchone()
        return int(row["total"])

    def top_addresses(self, limit: int = 20) -> list[AddressBalance]:
        rows = self._conn.execute(
            "SELECT address, SUM(lovelace) AS bal FROM tx_out "
            "WHERE consumed_by_tx_id IS NULL GROUP BY address ORDER BY bal DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [AddressBalance(address=r["address"], balance=int(r["bal"])) for r in rows]

    def top_stake_accounts(self, limit: int = 20) -> list[StakeAccountBalance]:
        rows = self._conn.execute(
            "SELECT stake_cred, SUM(lovelace) AS bal FROM tx_out "
            "WHERE consumed_by_tx_id IS NULL AND stake_cred IS NOT NULL "
            "GROUP BY stake_cred ORDER BY bal DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            StakeAccountBalance(stake_credential=r["stake_cred"], controlled_stake=int(r["bal"]))
            for r in rows
        ]

    def dreps(self) -> tuple[str, ...]:
        rows = self._conn.execute(
            "SELECT DISTINCT drep_id FROM drep_registration "
            "WHERE drep_id NOT IN (SELECT drep_id FROM drep_deregistration) "
            "ORDER BY drep_id"
        ).fetchall()
        return tuple(r["drep_id"] for r in rows)

    def governance_actions(self) -> tuple[str, ...]:
        rows = self._conn.execute(
            "SELECT gov_action_id FROM gov_action_proposal ORDER BY id"
        ).fetchall()
        return tuple(r["gov_action_id"] for r in rows)

    def vote_tally(self, gov_action_id: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT vote, COUNT(*) AS n FROM voting_procedure "
            "WHERE gov_action_id = ? GROUP BY vote",
            (gov_action_id,),
        ).fetchall()
        return {r["vote"]: int(r["n"]) for r in rows}

    def governance_action_summaries(self) -> list[GovActionSummary]:
        rows = self._conn.execute(
            "SELECT gov_action_id, action_type, deposit FROM gov_action_proposal ORDER BY id"
        ).fetchall()
        summaries: list[GovActionSummary] = []
        for r in rows:
            tally = self.vote_tally(r["gov_action_id"])
            summaries.append(
                GovActionSummary(
                    gov_action_id=r["gov_action_id"],
                    action_type=r["action_type"],
                    deposit=r["deposit"],
                    yes=tally.get("Yes", 0),
                    no=tally.get("No", 0),
                    abstain=tally.get("Abstain", 0),
                )
            )
        return summaries

    def protocol_updates(self) -> list[GovActionSummary]:
        kinds = {"ParameterChange", "HardForkInitiation"}
        return [s for s in self.governance_action_summaries() if s.action_type in kinds]

    def governance_action_votes(self, gov_action_id: str) -> tuple[GovVoteRecord, ...]:
        rows = self._conn.execute(
            "SELECT voter_role, voter_id, vote FROM voting_procedure "
            "WHERE gov_action_id = ? ORDER BY id",
            (gov_action_id,),
        ).fetchall()
        return tuple(
            GovVoteRecord(voter_role=r["voter_role"], voter_id=r["voter_id"], vote=r["vote"])
            for r in rows
        )

    def drep_summaries(self) -> list[DRepSummary]:
        summaries: list[DRepSummary] = []
        for drep_id in self.dreps():
            deposit = self._conn.execute(
                "SELECT deposit FROM drep_registration WHERE drep_id = ? "
                "ORDER BY tx_id DESC LIMIT 1",
                (drep_id,),
            ).fetchone()["deposit"]
            votes = self._conn.execute(
                "SELECT COUNT(*) AS n FROM voting_procedure "
                "WHERE voter_id = ? AND voter_role = 'DRep'",
                (drep_id,),
            ).fetchone()["n"]
            summaries.append(DRepSummary(drep_id=drep_id, deposit=deposit, votes_cast=votes))
        return summaries

    def drep_votes(self, drep_id: str) -> tuple[DRepVote, ...]:
        rows = self._conn.execute(
            "SELECT v.gov_action_id AS gid, v.vote AS vote, p.action_type AS action_type "
            "FROM voting_procedure v "
            "LEFT JOIN gov_action_proposal p ON p.gov_action_id = v.gov_action_id "
            "WHERE v.voter_id = ? AND v.voter_role = 'DRep' ORDER BY v.id",
            (drep_id,),
        ).fetchall()
        return tuple(
            DRepVote(
                gov_action_id=r["gid"],
                action_type=r["action_type"] or "Unknown",
                vote=r["vote"],
            )
            for r in rows
        )

    def committee_members(self) -> list[CommitteeMember]:
        # A member is any cold credential that authorized a hot key; its current
        # hot key is the latest such authorization, and it has resigned if a
        # resignation certificate exists for that cold credential.
        auths = self._conn.execute(
            "SELECT subject AS cold, detail AS hot FROM certificate "
            "WHERE cert_type = 'Committee Hot Key Authorization' ORDER BY id"
        ).fetchall()
        latest_hot: dict[str, str] = {}
        for r in auths:
            latest_hot[r["cold"]] = r["hot"]
        resigned = {
            r["cold"]
            for r in self._conn.execute(
                "SELECT DISTINCT subject AS cold FROM certificate "
                "WHERE cert_type = 'Committee Cold Key Resignation'"
            ).fetchall()
        }
        return [
            CommitteeMember(cold_credential=cold, hot_credential=hot, resigned=cold in resigned)
            for cold, hot in sorted(latest_hot.items())
        ]

    def committee_member(self, cold_credential: str) -> CommitteeMember | None:
        return next(
            (m for m in self.committee_members() if m.cold_credential == cold_credential), None
        )

    def blocks_in_epoch(self, epoch_no: int, epoch_length: int, limit: int = 200) -> list[Block]:
        rows = self._conn.execute(
            "SELECT hash FROM block WHERE slot_no / ? = ? ORDER BY block_no DESC LIMIT ?",
            (epoch_length, epoch_no, limit),
        ).fetchall()
        blocks = [self.get_block(r["hash"]) for r in rows]
        return [b for b in blocks if b is not None]

    def certificates(
        self, cert_type: str | None = None, limit: int = 200
    ) -> list[CertificateRecord]:
        sql = (
            "SELECT c.cert_type AS cert_type, c.subject AS subject, c.detail AS detail, "
            "t.hash AS tx_hash FROM certificate c JOIN tx t ON t.id = c.tx_id "
        )
        params: tuple[object, ...]
        if cert_type is None:
            sql += "ORDER BY c.id DESC LIMIT ?"
            params = (limit,)
        else:
            sql += "WHERE c.cert_type = ? ORDER BY c.id DESC LIMIT ?"
            params = (cert_type, limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [
            CertificateRecord(
                cert_type=r["cert_type"],
                subject=r["subject"],
                detail=r["detail"],
                tx_hash=r["tx_hash"],
            )
            for r in rows
        ]

    def certificate_summary(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            "SELECT cert_type, COUNT(*) AS n FROM certificate GROUP BY cert_type ORDER BY cert_type"
        ).fetchall()
        return [(r["cert_type"], r["n"]) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
