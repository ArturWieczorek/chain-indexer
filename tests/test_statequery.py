"""Tests for the local-state-query codec, against real captured result fixtures."""

from pathlib import Path
from typing import Any

import cbor2

from chainidx import statequery
from chainidx.model import PoolStake

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return cbor2.loads((FIXTURES / name).read_bytes())


def test_message_builders() -> None:
    assert statequery.acquire_message() == [8]
    assert statequery.release_message() == [5]
    assert statequery.system_start_message() == [3, [1]]
    # Era-wrapped block queries: [3, [0, [0, [conway=6, shelley_query]]]].
    assert statequery.epoch_query() == [3, [0, [0, [6, [1]]]]]
    assert statequery.stake_pools_query() == [3, [0, [0, [6, [16]]]]]
    assert statequery.stake_distribution_query() == [3, [0, [0, [6, [5]]]]]
    assert statequery.protocol_params_query() == [3, [0, [0, [6, [3]]]]]


def test_delegations_and_rewards_query_and_parse() -> None:
    cred = "e9546949f50285fd15493fe5ba3ffc8bac4aef1c34f5a294d66be825"
    pool = "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0"
    query = statequery.delegations_and_rewards_query([cred])
    assert query == [3, [0, [0, [6, [10, [[0, bytes.fromhex(cred)]]]]]]]

    # Result shape: [[delegations, rewards]] keyed by (keyType, credential).
    result = [
        [
            {(0, bytes.fromhex(cred)): bytes.fromhex(pool)},
            {(0, bytes.fromhex(cred)): 602474899},
        ]
    ]
    parsed = statequery.parse_delegations_and_rewards(result)
    assert parsed[cred].delegated_pool == pool
    assert parsed[cred].reward == 602474899

    # A credential with a reward but no delegation has delegated_pool None.
    reward_only = statequery.parse_delegations_and_rewards([[{}, {(0, bytes.fromhex(cred)): 5}]])
    assert reward_only[cred].delegated_pool is None
    assert reward_only[cred].reward == 5


def test_parse_epoch() -> None:
    assert statequery.parse_epoch([76]) == 76


def test_parse_system_start() -> None:
    # [year, day-of-year, picoseconds-of-day]; day 194 of 2026 is 13 July.
    iso = statequery.parse_system_start([2026, 194, 74212000000000000])
    assert iso.startswith("2026-07-13T")


def test_parse_stake_pools() -> None:
    pools = statequery.parse_stake_pools(load("lsq_stake_pools.cbor"))
    assert len(pools) == 3
    assert all(len(p) == 56 for p in pools)  # 28-byte hashes as hex
    assert list(pools) == sorted(pools)


def test_parse_stake_distribution() -> None:
    dist = statequery.parse_stake_distribution(load("lsq_stake_distribution.cbor"))
    assert len(dist) == 3
    assert all(isinstance(p, PoolStake) for p in dist)
    assert all(0.0 <= p.stake <= 1.0 for p in dist)
    # Sorted by stake, largest first.
    assert [p.stake for p in dist] == sorted((p.stake for p in dist), reverse=True)


def test_parse_protocol_params() -> None:
    params = statequery.parse_protocol_params(load("lsq_pparams.cbor"))
    assert params["min_fee_a"] == 44
    assert params["min_fee_b"] == 155381
    assert params["key_deposit"] == 400000
    assert params["pool_deposit"] == 500000000
    assert params["n_opt"] == 500
    assert params["coins_per_utxo_byte"] == 4310
