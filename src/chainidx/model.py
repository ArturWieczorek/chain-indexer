"""The domain model: the small set of types that describe a Cardano chain.

Everything else in this project reads or writes these types, so we keep them
simple, immutable, and free of behaviour that does not belong to the data
itself. They are ordinary Python dataclasses.

Why immutable (``frozen=True``)? A block that has been produced never changes -
if the chain wants a different block, it produces a new one with a new hash. By
freezing these values we get three things for free: they cannot be mutated by
accident, they compare by value (two blocks with the same fields are equal), and
they are hashable (so we can put points in a set when we compare two chains).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Asset:
    """A quantity of a native token (anything that is not ada/lovelace).

    A native asset is identified by the ``policy_id`` (the script that governs
    it) together with the ``asset_name``. On Cardano, ada itself is measured in
    ``lovelace`` (1 ada = 1,000,000 lovelace) and lives directly on the output;
    everything else is a native asset and lives in this list.
    """

    policy_id: str
    asset_name: str
    quantity: int


@dataclass(frozen=True)
class AssetDetail:
    """A native asset with its total held quantity and number of holders (ch31)."""

    policy_id: str
    asset_name: str
    quantity: int
    holders: int


@dataclass(frozen=True)
class PolicyDetail:
    """The native assets minted under one policy id (chapter 36).

    A policy id is the hash of the minting policy; every asset it can mint shares
    it. This groups them so a policy has a page of its own.
    """

    policy_id: str
    asset_count: int
    assets: tuple[AssetDetail, ...]


@dataclass(frozen=True)
class TxOut:
    """A transaction output: value sent to an address.

    An output is a parcel of value (some lovelace, plus zero or more native
    assets) addressed to someone. Until it is spent by a later transaction it is
    "unspent" - part of the UTxO set we will track from chapter 04.
    """

    address: str
    lovelace: int
    assets: tuple[Asset, ...] = ()


@dataclass(frozen=True)
class TxIn:
    """A transaction input: a reference to an earlier output being spent.

    An input does not carry value itself. It names an output to consume by the
    transaction that created it (``tx_id``) and that output's position within
    that transaction (``index``). Following these references backwards is how we
    know an address's balance.
    """

    tx_id: str
    index: int


@dataclass(frozen=True)
class StakeRegistration:
    """A stake address announcing itself to the ledger (chapter 06)."""

    stake_address: str


@dataclass(frozen=True)
class StakeDeregistration:
    """A stake address retiring itself (chapter 06)."""

    stake_address: str


@dataclass(frozen=True)
class StakeDelegation:
    """A stake address delegating its stake to a pool (chapter 06)."""

    stake_address: str
    pool_id: str


@dataclass(frozen=True)
class PoolRegistration:
    """A stake pool registering or updating its parameters (chapter 06).

    Real pool registration carries many more fields (cost, relays, owners,
    metadata). We keep a teaching subset.
    """

    pool_id: str
    pledge: int
    margin: float
    reward_address: str


@dataclass(frozen=True)
class PoolRetirement:
    """A stake pool scheduling its retirement at an epoch (chapter 06)."""

    pool_id: str
    retiring_epoch: int


@dataclass(frozen=True)
class DRepRegistration:
    """A delegated representative registering (Conway governance, chapter 07)."""

    drep_id: str
    deposit: int


@dataclass(frozen=True)
class DRepDeregistration:
    """A delegated representative retiring (chapter 07)."""

    drep_id: str


@dataclass(frozen=True)
class VoteDelegation:
    """A stake address delegating its vote to a DRep (Conway, chapter 34).

    ``drep`` is the target: a DRep credential (hex), or the special roles
    ``AlwaysAbstain`` / ``AlwaysNoConfidence``.
    """

    stake_address: str
    drep: str


@dataclass(frozen=True)
class DRepUpdate:
    """A DRep updating its metadata anchor (chapter 34)."""

    drep_id: str


@dataclass(frozen=True)
class CommitteeAuthHot:
    """A committee member authorizing a hot credential to vote (chapter 34)."""

    cold_credential: str
    hot_credential: str


@dataclass(frozen=True)
class CommitteeResignCold:
    """A committee member resigning its cold credential (chapter 34)."""

    cold_credential: str


# A certificate is any one of these. Transactions carry a list of them.
Certificate = (
    StakeRegistration
    | StakeDeregistration
    | StakeDelegation
    | PoolRegistration
    | PoolRetirement
    | DRepRegistration
    | DRepDeregistration
    | VoteDelegation
    | DRepUpdate
    | CommitteeAuthHot
    | CommitteeResignCold
)


@dataclass(frozen=True)
class CertificateRecord:
    """A certificate as the Certificates browser lists it (chapter 34).

    ``cert_type`` is a human category label (for example ``Delegation`` or
    ``Committee Hot Key Authorization``); ``subject`` is the primary id it acts on
    (a stake, pool, DRep, or committee credential); ``detail`` is a secondary field
    (the pool for a delegation, the epoch for a retirement, and so on).
    """

    cert_type: str
    subject: str
    detail: str
    tx_hash: str


@dataclass(frozen=True)
class GovActionProposal:
    """A governance action proposed on-chain (chapter 07).

    ``action_type`` is one of Cardano's governance action kinds, for example
    ``ParameterChange``, ``TreasuryWithdrawals``, ``NoConfidence``,
    ``NewConstitution``, or ``InfoAction``.
    """

    gov_action_id: str
    action_type: str
    deposit: int
    return_address: str


@dataclass(frozen=True)
class GovVote:
    """A vote cast on a governance action (chapter 07).

    ``voter_role`` is ``ConstitutionalCommittee``, ``DRep``, or ``SPO``.
    ``vote`` is ``Yes``, ``No``, or ``Abstain``.
    """

    gov_action_id: str
    voter_role: str
    voter_id: str
    vote: str


@dataclass(frozen=True)
class Tx:
    """A transaction: it consumes some inputs and creates some outputs.

    This is a deliberately small view of a Cardano transaction. It also carries
    the ``certificates`` (staking and pool actions) and, from chapter 07, the
    governance actions and votes we index. Real transactions have more still
    (metadata, scripts, witnesses); we add fields only as we index them.
    """

    tx_id: str
    inputs: tuple[TxIn, ...] = ()
    outputs: tuple[TxOut, ...] = ()
    certificates: tuple[Certificate, ...] = ()
    proposals: tuple[GovActionProposal, ...] = ()
    votes: tuple[GovVote, ...] = ()
    withdrawals: tuple[Withdrawal, ...] = ()
    fee: int = 0
    metadata: str = ""  # a JSON string of the transaction's metadata, or ""


@dataclass(frozen=True)
class Point:
    """A position on the chain: a slot number plus the block hash at that slot.

    A slot number alone is not enough to name a position, because a fork can put
    two different blocks at the same slot. Pairing the slot with the block hash
    makes a point unambiguous. Points are how the chain-sync protocol says "I am
    here" and "back up to here".
    """

    slot_no: int
    block_hash: str


@dataclass(frozen=True)
class ResolvedInput:
    """An input with the value it spends filled in from the output it consumes.

    An input only names an earlier output (``tx_id`` and ``index``). To show what
    it is worth, we look that output up and copy its ``address``, ``lovelace``, and
    ``assets`` here. If we never indexed that output (syncing from mid-chain), the
    address is empty and the value zero.
    """

    tx_id: str
    index: int
    address: str
    lovelace: int
    assets: tuple[Asset, ...] = ()


@dataclass(frozen=True)
class Withdrawal:
    """A withdrawal of staking rewards from a reward account (chapter 39).

    ``stake_address`` is the reward account (a stake address, hex); ``amount`` is
    the lovelace withdrawn.
    """

    stake_address: str
    amount: int


@dataclass(frozen=True)
class WithdrawalRecord:
    """A withdrawal as the browse list reports it, with its transaction (ch39)."""

    stake_address: str
    amount: int
    tx_hash: str


@dataclass(frozen=True)
class CommitteeMember:
    """A constitutional committee member, derived from certificates (chapter 38).

    A member authorizes a hot credential to vote on its behalf (``hot_credential``);
    ``resigned`` is true once the member has resigned its cold credential.
    """

    cold_credential: str
    hot_credential: str
    resigned: bool


@dataclass(frozen=True)
class TxDetail:
    """A transaction as the query API reports it (chapter 35).

    Inputs are resolved to the value they spend; outputs carry their assets; and
    the transaction's ``fee`` and any ``metadata`` (a JSON string, empty when the
    transaction carried none) round out the picture for the detail page.
    """

    tx_id: str
    block_hash: str
    inputs: tuple[ResolvedInput, ...]
    outputs: tuple[TxOut, ...]
    fee: int = 0
    metadata: str = ""


@dataclass(frozen=True)
class PoolSummary:
    """A stake pool as the explorer shows it (chapter 22).

    ``blocks_minted`` and ``delegators`` come from the indexed chain; ``pledge``
    and ``margin`` from the pool's latest registration. Live stake needs
    local-state-query and is added later.
    """

    pool_id: str
    blocks_minted: int
    delegators: int
    pledge: int
    margin: float
    reward_address: str
    live_stake: float = 0.0  # fraction of total active stake (ledger state, chapter 24)
    saturation: float = 0.0  # live_stake relative to the ideal 1/n_opt share


@dataclass(frozen=True)
class EpochSummary:
    """Aggregate stats for one epoch, derived from the indexed blocks (chapter 21)."""

    epoch_no: int
    block_count: int
    tx_count: int
    start_slot: int
    end_slot: int


@dataclass(frozen=True)
class GovActionSummary:
    """A governance action with its vote tally (chapter 23)."""

    gov_action_id: str
    action_type: str
    deposit: int
    yes: int
    no: int
    abstain: int


@dataclass(frozen=True)
class GovVoteRecord:
    """A single vote cast on a governance action (chapter 23).

    ``gov_action_id`` is populated when the vote is listed from a transaction's
    side (chapter 37), so the vote can link to the action it refers to; it stays
    empty when votes are listed for a known action.
    """

    voter_role: str
    voter_id: str
    vote: str
    gov_action_id: str = ""


@dataclass(frozen=True)
class DRepSummary:
    """A delegated representative with its deposit and vote count (chapter 23)."""

    drep_id: str
    deposit: int
    votes_cast: int


@dataclass(frozen=True)
class DRepVote:
    """A single vote a DRep cast, seen from the DRep's side (chapter 33).

    ``action_type`` is the type of the governance action the vote refers to, or
    ``"Unknown"`` if the referenced action has not been indexed (it may live in a
    block we have not reached, or on another chain).
    """

    gov_action_id: str
    action_type: str
    vote: str


@dataclass(frozen=True)
class AccountState:
    """A stake account's delegation and reward balance (chapter 26, ledger state).

    ``stake_address`` is the stake credential (hex); ``delegated_pool`` is the pool
    it delegates to (hex), or ``None``; ``reward`` is the withdrawable reward
    balance in lovelace.
    """

    stake_address: str
    delegated_pool: str | None
    reward: int


@dataclass(frozen=True)
class PoolStake:
    """A stake pool's share of the live stake (chapter 20, from local-state-query).

    ``stake`` is the pool's fraction of the total active stake, in [0, 1].
    """

    pool_id: str
    stake: float


@dataclass(frozen=True)
class LedgerSnapshot:
    """A point-in-time view of ledger state, from local-state-query (chapter 20).

    This is data the chain does not carry in its blocks - the node computes it -
    so it can only be read by querying the node's ledger state.
    """

    epoch: int
    system_start: str
    protocol_params: dict[str, int]
    stake_pools: tuple[str, ...]
    stake_distribution: tuple[PoolStake, ...]


@dataclass(frozen=True)
class TxActivity:
    """What a transaction did beyond moving value (chapter 28): its certificates
    and governance actions/votes, as short human-readable descriptions."""

    certificates: tuple[str, ...]
    proposals: tuple[str, ...]
    votes: tuple[str, ...]


@dataclass(frozen=True)
class Origin:
    """The position before the first block (the genesis boundary).

    Chain-sync can roll us back to before block one. We mark that with this value
    rather than reusing ``None``, which we keep for "no intersection found". Being
    a frozen dataclass, all ``Origin()`` values are equal and hashable, so
    ``ORIGIN`` behaves like a singleton for comparisons.
    """


ORIGIN = Origin()


@dataclass(frozen=True)
class Tip:
    """The newest block the node knows about: its point and its height.

    The node reports its tip alongside every message so a follower can tell how
    far behind it is.
    """

    point: Point
    block_no: int


@dataclass(frozen=True)
class Block:
    """One block in the chain.

    A block has a height (``block_no``), a ``slot_no`` (when it was made), its own
    ``block_hash``, the ``prev_hash`` of the block it builds on, and the
    transactions it carries. The ``prev_hash`` link is what turns a pile of
    blocks into a chain.
    """

    block_no: int
    slot_no: int
    block_hash: str
    prev_hash: str
    txs: tuple[Tx, ...] = field(default=())
    issuer: str = ""  # the pool id that minted the block (chapter 22), or ""

    @property
    def point(self) -> Point:
        """Where this block sits on the chain."""
        return Point(slot_no=self.slot_no, block_hash=self.block_hash)

    def links_onto(self, parent: Block) -> bool:
        """True if this block builds directly on ``parent``.

        A block builds on another when its ``prev_hash`` equals the parent's
        ``block_hash``. This one check is the seed of fork detection in the next
        chapter: a block that does not link onto our current tip belongs to a
        different branch.
        """
        return self.prev_hash == parent.block_hash
