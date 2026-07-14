"""The local-state-query mini-protocol: messages and result parsing (pure part).

Local-state-query (LSQ) is the node-to-client conversation that lets a client read
the node's **ledger state** - data the chain does not carry in its blocks, so it
can only be obtained by asking the node to compute it: the current epoch, protocol
parameters, and the live stake distribution across pools.

The conversation is a small state machine:

```
  us -> node:  [8]              MsgAcquire (the current/volatile tip)
  node -> us:  [1]              MsgAcquired
  node -> us:  [2, failure]     MsgFailure
  us -> node:  [3, query]       MsgQuery
  node -> us:  [4, result]      MsgResult
  us -> node:  [5]              MsgRelease
```

The fiddly part is the query encoding. A ledger query is wrapped twice by the
hard-fork combinator: `[0, [0, [era, shelley_query]]]` - the outer `0` selects a
block query, the inner `0` selects "the current era", and `era` (6 for Conway)
picks which era's query language to use. Querying the wrong era does not error; the
node replies with an era-mismatch result, which is why the era must be right. All
of these shapes were confirmed by probing a live node, not guessed.

This module is the pure codec (message builders + result parsers), tested against
result fixtures captured from a live node. The socket-driving `LocalStateClient`
lives in ``localstate.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from chainidx.model import AccountState, PoolStake

# Conway's index in the node's era list (Byron=0 ... Conway=6).
_CONWAY_ERA = 6

# Shelley-family block-query tags (the ones we use).
_GET_EPOCH_NO = [1]
_GET_CURRENT_PPARAMS = [3]
_GET_STAKE_DISTRIBUTION = [5]
_GET_STAKE_POOLS = [16]


def acquire_message() -> list[Any]:
    """MsgAcquire the volatile tip (the latest ledger state)."""
    return [8]


def release_message() -> list[Any]:
    """MsgRelease the acquired state."""
    return [5]


def system_start_message() -> list[Any]:
    """MsgQuery GetSystemStart (a consensus query, not era-wrapped)."""
    return [3, [1]]


def _block_query(shelley_query: list[Any]) -> list[Any]:
    """Wrap an era-specific query as a current-era block query, in a MsgQuery."""
    return [3, [0, [0, [_CONWAY_ERA, shelley_query]]]]


def epoch_query() -> list[Any]:
    return _block_query(_GET_EPOCH_NO)


def stake_pools_query() -> list[Any]:
    return _block_query(_GET_STAKE_POOLS)


def stake_distribution_query() -> list[Any]:
    return _block_query(_GET_STAKE_DISTRIBUTION)


def protocol_params_query() -> list[Any]:
    return _block_query(_GET_CURRENT_PPARAMS)


def delegations_and_rewards_query(credentials: list[str]) -> list[Any]:
    """GetFilteredDelegationsAndRewardAccounts for a set of stake credentials.

    This is our first query that carries an argument: a list of ``[keyType,
    hash]`` credentials (keyType 0 = key hash). The node returns the pool each
    delegates to and its reward balance.
    """
    creds = [[0, bytes.fromhex(c)] for c in credentials]
    return _block_query([10, creds])


def parse_delegations_and_rewards(result: list[Any]) -> dict[str, AccountState]:
    """Parse the result into ``{credential_hex: AccountState}``.

    The result is ``[[delegations, rewards]]`` where each map is keyed by a
    ``(keyType, credential)`` pair.
    """
    delegations, rewards = result[0]
    out: dict[str, AccountState] = {}
    for key, pool in delegations.items():
        cred = key[1].hex()
        out[cred] = AccountState(stake_address=cred, delegated_pool=pool.hex(), reward=0)
    for key, coin in rewards.items():
        cred = key[1].hex()
        pool = out[cred].delegated_pool if cred in out else None
        out[cred] = AccountState(stake_address=cred, delegated_pool=pool, reward=int(coin))
    return out


def parse_epoch(result: list[Any]) -> int:
    """GetEpochNo result is ``[epoch]``."""
    return int(result[0])


def parse_system_start(result: list[Any]) -> str:
    """GetSystemStart result is ``[year, day_of_year, picoseconds_of_day]``."""
    year, day_of_year, picoseconds = result
    start = datetime(year, 1, 1, tzinfo=UTC) + timedelta(
        days=day_of_year - 1, microseconds=picoseconds // 1_000_000
    )
    return start.isoformat()


def parse_stake_pools(result: list[Any]) -> tuple[str, ...]:
    """GetStakePools result is ``[{pool_id_bytes, ...}]`` (a set)."""
    return tuple(sorted(pool_id.hex() for pool_id in result[0]))


def parse_stake_distribution(result: list[Any]) -> tuple[PoolStake, ...]:
    """GetStakeDistribution result is ``[{pool_id: [stake_fraction, vrf]}]``."""
    pools = [
        PoolStake(pool_id=pool_id.hex(), stake=float(value[0]))
        for pool_id, value in result[0].items()
    ]
    return tuple(sorted(pools, key=lambda p: p.stake, reverse=True))


def parse_protocol_params(result: list[Any]) -> dict[str, int]:
    """GetCurrentPParams result is ``[[positional params...]]`` (Conway order)."""
    p = result[0]
    return {
        "min_fee_a": p[0],
        "min_fee_b": p[1],
        "max_block_body_size": p[2],
        "max_tx_size": p[3],
        "max_block_header_size": p[4],
        "key_deposit": p[5],
        "pool_deposit": p[6],
        "n_opt": p[8],  # target number of pools; used for saturation
        "min_pool_cost": p[13],
        "coins_per_utxo_byte": p[14],
    }
