# chain-indexer REST API reference

The chain-indexer exposes a read-only REST API over the data it indexes from the
Cardano chain: blocks, transactions, addresses, native assets, stake pools,
Conway-era governance, certificates, withdrawals, epochs, and a few analytics
rollups. The endpoint shapes take inspiration from Blockfrost (`/blocks/latest`,
`/txs/{hash}`, `/addresses/{addr}`), with a kupo-style watch/match facility layered
on top. Every response is JSON. The default base URL is `http://127.0.0.1:8000`
(started with `make api`). An interactive Swagger UI that lets you try every
endpoint live is served at `/docs`, and a ReDoc rendering at `/redoc`.

All examples below were captured from the running application against a small,
representative indexed dataset (a pool, some funded addresses, native and CIP-68
assets, governance actions and votes, certificates, and a withdrawal). The values
are synthetic but the field names, types, and structure match the code exactly.

## Conventions

- Base URL: `http://127.0.0.1:8000` unless configured otherwise.
- Path parameters are written `{like_this}`. Hashes and ids are lower-case hex;
  addresses, stake addresses, and pool ids may be supplied in bech32
  (`addr_test1...`, `stake_test1...`, `pool1...`) or raw hex, and are echoed back
  in bech32 where the API can encode them.
- Query parameters are appended as `?name=value`. Where a `limit` is accepted it
  defaults as noted per endpoint.
- A governance action id contains a `#` (for example `...a5b#0`). In a URL the
  `#` must be percent-encoded as `%23`, otherwise it is treated as a fragment and
  the server sees a different id.
- Times (`time`, `start_time`, `end_time`, `tip_time`, `registered_time`) and the
  `/epochs`, `/network`, `/analytics/timeseries` bodies only appear when the app
  was started with network parameters (a Shelley genesis via `CHAINIDX_GENESIS`).
  Without them, time fields are omitted and `/epochs` returns `[]`.
- Errors use the FastAPI convention: an HTTP status code plus a JSON body
  `{"detail": "..."}`. A missing resource is `404`; an invalid query value is
  `422`. For example:

  ```json
  {
    "detail": "block not found"
  }
  ```

---

## Meta

### GET /health

Liveness probe and current tip height.

Example request:

```bash
curl http://127.0.0.1:8000/health
```

```json
{
  "status": "ok",
  "tip_height": 3
}
```

`status` is always `"ok"` when the service is up. `tip_height` is the block
number of the newest indexed block, or `null` when the store is empty.

### GET /config

Client-side configuration the block explorer reads.

Example request:

```bash
curl http://127.0.0.1:8000/config
```

```json
{
  "ipfs_gateway": "https://ipfs.io/ipfs/"
}
```

`ipfs_gateway` is the HTTP gateway the explorer uses to render `ipfs://` images
(for example NFT artwork). It is `null` unless `CHAINIDX_IPFS_GATEWAY` is set.

### GET /network

Network parameters and where the chain tip sits in epoch/wall-clock terms.

Example request:

```bash
curl http://127.0.0.1:8000/network
```

```json
{
  "available": true,
  "system_start": "2022-09-01T21:44:51Z",
  "slot_length": 1.0,
  "epoch_length": 432000,
  "current_epoch": 1,
  "slot_in_epoch": 10,
  "epoch_progress": 0.0,
  "tip_time": "2022-09-06T21:45:01+00:00",
  "tip_height": 3
}
```

`system_start`, `slot_length` (seconds per slot), and `epoch_length` (slots per
epoch) come from the genesis. The `current_epoch`, `slot_in_epoch`,
`epoch_progress` (fraction in `[0, 1)`), `tip_time`, and `tip_height` block
describes the tip and is present only when at least one block is indexed. When the
app has no network parameters, the body is simply `{"available": false}`.

### GET /protocol-parameters

The most recent protocol-parameter snapshot the indexer has recorded.

Example request:

```bash
curl http://127.0.0.1:8000/protocol-parameters
```

```json
{
  "key_deposit": 2000000,
  "max_block_size": 90112,
  "max_tx_size": 16384,
  "min_fee_a": 44,
  "min_fee_b": 155381,
  "n_opt": 500,
  "pool_deposit": 500000000
}
```

A flat map of integer protocol parameters. The exact keys mirror whatever the
node reported; an empty object `{}` means none have been recorded yet.

---

## Blocks

### GET /blocks

The most recent blocks, newest first.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `limit` | int | 20 | Maximum number of blocks to return. |

Example request:

```bash
curl "http://127.0.0.1:8000/blocks?limit=3"
```

```json
[
  {
    "hash": "c4e1222222222222222222222222222222222222222222222222222222222222",
    "block_no": 3,
    "slot_no": 432010,
    "prev_hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
    "tx_count": 1,
    "tx_hashes": [
      "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02"
    ],
    "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
    "epoch_no": 1,
    "time": "2022-09-06T21:45:01+00:00"
  },
  {
    "hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
    "block_no": 2,
    "slot_no": 20,
    "prev_hash": "3f8a000000000000000000000000000000000000000000000000000000000000",
    "tx_count": 1,
    "tx_hashes": [
      "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1"
    ],
    "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
    "epoch_no": 0,
    "time": "2022-09-01T21:45:11+00:00"
  },
  {
    "hash": "3f8a000000000000000000000000000000000000000000000000000000000000",
    "block_no": 1,
    "slot_no": 10,
    "prev_hash": "genesis",
    "tx_count": 1,
    "tx_hashes": [
      "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0"
    ],
    "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
    "epoch_no": 0,
    "time": "2022-09-01T21:45:01+00:00"
  }
]
```

Each block carries its `hash`, height (`block_no`), `slot_no`, the `prev_hash` it
builds on, its transaction count and the list of `tx_hashes`. `issuer` (the
minting pool, as a `pool1...` id) is present when known. `epoch_no` and `time`
appear only when network parameters are configured.

### GET /blocks/latest

The current tip block.

Example request:

```bash
curl http://127.0.0.1:8000/blocks/latest
```

```json
{
  "hash": "c4e1222222222222222222222222222222222222222222222222222222222222",
  "block_no": 3,
  "slot_no": 432010,
  "prev_hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
  "tx_count": 1,
  "tx_hashes": [
    "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02"
  ],
  "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
  "epoch_no": 1,
  "time": "2022-09-06T21:45:01+00:00"
}
```

Same block shape as `/blocks`. Returns `404` with `{"detail": "no blocks indexed
yet"}` on an empty store.

### GET /blocks/{block_hash}

A single block by its hash.

| Path param | Description |
|------------|-------------|
| `block_hash` | The block's hash (hex). |

Example request:

```bash
curl http://127.0.0.1:8000/blocks/3f8a000000000000000000000000000000000000000000000000000000000000
```

```json
{
  "hash": "3f8a000000000000000000000000000000000000000000000000000000000000",
  "block_no": 1,
  "slot_no": 10,
  "prev_hash": "genesis",
  "tx_count": 1,
  "tx_hashes": [
    "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0"
  ],
  "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
  "epoch_no": 0,
  "time": "2022-09-01T21:45:01+00:00"
}
```

Returns `404` with `{"detail": "block not found"}` if no block has that hash.

### GET /blocks/height/{height}

A single block by its height (block number).

| Path param | Description |
|------------|-------------|
| `height` | The block number (integer). |

Example request:

```bash
curl http://127.0.0.1:8000/blocks/height/2
```

```json
{
  "hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
  "block_no": 2,
  "slot_no": 20,
  "prev_hash": "3f8a000000000000000000000000000000000000000000000000000000000000",
  "tx_count": 1,
  "tx_hashes": [
    "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1"
  ],
  "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
  "epoch_no": 0,
  "time": "2022-09-01T21:45:11+00:00"
}
```

Returns `404` with `{"detail": "no block at that height"}` if the height is not
indexed.

### GET /blocks/slot/{slot}

A single block by the slot it was minted in.

| Path param | Description |
|------------|-------------|
| `slot` | The slot number (integer). |

Example request:

```bash
curl http://127.0.0.1:8000/blocks/slot/20
```

```json
{
  "hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
  "block_no": 2,
  "slot_no": 20,
  "prev_hash": "3f8a000000000000000000000000000000000000000000000000000000000000",
  "tx_count": 1,
  "tx_hashes": [
    "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1"
  ],
  "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
  "epoch_no": 0,
  "time": "2022-09-01T21:45:11+00:00"
}
```

Returns `404` with `{"detail": "no block at that slot"}` if no block sits at that
slot.

---

## Transactions

### GET /transactions

The most recent transactions, newest first.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `limit` | int | 20 | Maximum number of transactions to return. |

Example request:

```bash
curl "http://127.0.0.1:8000/transactions?limit=3"
```

```json
[
  {
    "tx_id": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02",
    "block_hash": "c4e1222222222222222222222222222222222222222222222222222222222222",
    "block_no": 3,
    "fee": 195000,
    "output_count": 2,
    "total_output": 6000000,
    "time": "2022-09-06T21:45:01+00:00"
  },
  {
    "tx_id": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1",
    "block_hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
    "block_no": 2,
    "fee": 182000,
    "output_count": 2,
    "total_output": 99500000,
    "time": "2022-09-01T21:45:11+00:00"
  },
  {
    "tx_id": "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0",
    "block_hash": "3f8a000000000000000000000000000000000000000000000000000000000000",
    "block_no": 1,
    "fee": 178000,
    "output_count": 2,
    "total_output": 350000000,
    "time": "2022-09-01T21:45:01+00:00"
  }
]
```

A lightweight per-transaction summary: which block it is in (`block_hash`,
`block_no`), the `fee` (lovelace), and how many outputs (`output_count`) for how
much `total_output` (lovelace). `time` appears only with network parameters.

### GET /txs/{tx_hash}

The full detail of one transaction: resolved inputs, outputs, and everything the
transaction did on-chain (certificates, governance proposals, votes, withdrawals).

| Path param | Description |
|------------|-------------|
| `tx_hash` | The transaction hash (hex). |

Example request:

```bash
curl http://127.0.0.1:8000/txs/a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1
```

```json
{
  "tx_id": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1",
  "block_hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
  "fee": 182000,
  "metadata": null,
  "inputs": [
    {
      "tx_id": "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0",
      "index": 0,
      "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
      "lovelace": 100000000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 1000
        }
      ],
      "resolved": true
    }
  ],
  "outputs": [
    {
      "address": "addr_test1qzctpv9skzctpv9skzctpv9skzctpv9skzctpv9skzctpvzmtdd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtddslhltfz",
      "lovelace": 40000000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 400
        }
      ],
      "datum_hash": "fcaa61fb85676101d9e3398a484674e71c45c3fd41b492682f3b0054f4cf3273"
    },
    {
      "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
      "lovelace": 59500000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 600
        }
      ],
      "datum_hash": ""
    }
  ],
  "certificates": [],
  "proposals": [
    {
      "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#0",
      "action_type": "InfoAction",
      "deposit": 0
    },
    {
      "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#1",
      "action_type": "ParameterChange",
      "deposit": 100000000000
    }
  ],
  "votes": [
    {
      "voter_role": "DRep",
      "voter_id": "d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1",
      "vote": "Yes",
      "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#0"
    },
    {
      "voter_role": "SPO",
      "voter_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
      "vote": "Abstain",
      "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#0"
    }
  ],
  "withdrawals": []
}
```

`inputs` are resolved: each names the output it consumes (`tx_id`, `index`) and
carries that output's `address`, `lovelace`, and `assets`. `resolved` is `false`
when the consumed output was never indexed (a genesis/faucet UTxO), in which case
`address` is `""` and `lovelace` is `0`. `outputs` carry their `assets` (each an
`{policy_id, asset_name, quantity}` triple, both ids hex) and a `datum_hash`
(`""` if none). `metadata` is the decoded JSON of the transaction's metadata, or
`null`. `certificates`, `proposals`, `votes`, and `withdrawals` list the on-chain
actions this transaction carried (see the Certificates, Governance, and
Withdrawals sections for their shapes; here they are empty or governance-only).
Returns `404` with `{"detail": "transaction not found"}` for an unknown hash.

---

## Addresses and accounts

### GET /addresses/{address}

The balance and unspent outputs (UTxOs) of a payment address.

| Path param | Description |
|------------|-------------|
| `address` | A bech32 (`addr_test1...` / `addr1...`) or raw-hex payment address. |

Example request:

```bash
curl http://127.0.0.1:8000/addresses/addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu
```

```json
{
  "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
  "balance": 59500000,
  "utxos": [
    {
      "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
      "lovelace": 59500000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 600
        }
      ],
      "datum_hash": ""
    }
  ]
}
```

`address` echoes the queried value. `balance` is the total unspent lovelace.
`utxos` lists the address's current unspent outputs, each with the same output
shape as a transaction output. An address with no unspent outputs returns
`balance: 0` and `utxos: []`.

### GET /accounts/{stake_address}

The staking state of a reward/stake account.

| Path param | Description |
|------------|-------------|
| `stake_address` | A bech32 (`stake_test1...` / `stake1...`) stake address, or a raw credential hex. |

Example request:

```bash
curl http://127.0.0.1:8000/accounts/stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75
```

```json
{
  "stake_address": "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75",
  "credential": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
  "registered": false,
  "delegated_to": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
  "reward": 4200000,
  "controlled_stake": 59500000
}
```

`credential` is the 28-byte stake credential (hex) decoded from the address.
`registered` reflects the latest stake registration/deregistration certificate
seen for the credential; it is `false` here because a later transaction carried
this account's Stake Key Deregistration (certificates are cumulative, and the most
recent one wins). `delegated_to` is the pool the account delegates to (as a
`pool1...` id) or `null`. `reward` is the withdrawable reward balance (lovelace),
and `controlled_stake` is the total lovelace held by addresses that carry this
stake credential. Unknown accounts return the same shape with `registered: false`,
`delegated_to: null`, and zeroed amounts.

---

## Assets and policies

### GET /assets

Every native asset the indexer has seen, with its total held quantity.

Example request:

```bash
curl http://127.0.0.1:8000/assets
```

```json
[
  {
    "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
    "asset_name": "000643b0436c75623639",
    "quantity": 1
  },
  {
    "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
    "asset_name": "000de140436c75623639",
    "quantity": 1
  },
  {
    "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
    "asset_name": "436861696e",
    "quantity": 1000
  }
]
```

Each entry identifies an asset by `policy_id` and `asset_name` (both hex) and
gives its `quantity` currently held across all outputs.

### GET /assets/mints

Recent mint and burn events, newest first.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `limit` | int | 50 | Maximum number of mint/burn records to return. |

Example request:

```bash
curl http://127.0.0.1:8000/assets/mints
```

```json
[
  {
    "tx_hash": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02",
    "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
    "asset_name": "000643b0436c75623639",
    "asset_name_text": "",
    "quantity": 1
  },
  {
    "tx_hash": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02",
    "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
    "asset_name": "000de140436c75623639",
    "asset_name_text": "",
    "quantity": 1
  },
  {
    "tx_hash": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1",
    "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
    "asset_name": "436861496e644e4654",
    "asset_name_text": "ChaIndNFT",
    "quantity": 1
  }
]
```

Each record links a mint/burn to the `tx_hash` it happened in. `quantity` is
positive for a mint and negative for a burn. `asset_name_text` is the asset name
decoded as printable UTF-8, or `""` when it is not printable text (for example the
CIP-68 reference/user names above, which begin with a binary asset-name label).

### GET /assets/{policy_id}/{asset_name}

Detail for one native asset, including CIP-25 or CIP-68 metadata when present.

| Path param | Description |
|------------|-------------|
| `policy_id` | The minting policy id (hex). |
| `asset_name` | The asset name (hex). |

Example request (a plain token, no metadata):

```bash
curl http://127.0.0.1:8000/assets/6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0/436861696e
```

```json
{
  "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
  "asset_name": "436861696e",
  "asset_name_text": "Chain",
  "quantity": 1000,
  "holders": 2,
  "metadata": null,
  "metadata_standard": null
}
```

Example request (a CIP-68 user token that resolves its metadata from the matching
reference token's inline datum):

```bash
curl http://127.0.0.1:8000/assets/1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d/000de140436c75623639
```

```json
{
  "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
  "asset_name": "000de140436c75623639",
  "asset_name_text": "",
  "quantity": 1,
  "holders": 1,
  "metadata": {
    "name": "Club 69 Membership",
    "image": "ipfs://QmClub69Badge"
  },
  "metadata_standard": "CIP-68"
}
```

`quantity` is the total held; `holders` is how many distinct addresses hold it.
`metadata_standard` is `"CIP-25"` (from the mint transaction's `721` metadata),
`"CIP-68"` (parsed from the reference token's inline datum), or `null` when no
metadata is found; `metadata` carries the corresponding object (or `null`).
Returns `404` with `{"detail": "asset not found"}` for an unknown asset.

### GET /policies/{policy_id}

Every asset minted under one policy id.

| Path param | Description |
|------------|-------------|
| `policy_id` | The minting policy id (hex). |

Example request:

```bash
curl http://127.0.0.1:8000/policies/1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d
```

```json
{
  "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
  "asset_count": 2,
  "assets": [
    {
      "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
      "asset_name": "000643b0436c75623639",
      "asset_name_text": "",
      "quantity": 1,
      "holders": 1
    },
    {
      "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
      "asset_name": "000de140436c75623639",
      "asset_name_text": "",
      "quantity": 1,
      "holders": 1
    }
  ]
}
```

`asset_count` is how many distinct assets the policy has minted; `assets` lists
each with the same per-asset detail shape as `/assets/{policy_id}/{asset_name}`
(minus the metadata fields). Returns `404` with `{"detail": "policy not found"}`
for an unknown policy.

---

## Watch and matches (kupo-style)

These two endpoints implement a kupo-style watch/match facility: look up the
outputs matching a pattern, and resolve a datum by its hash. Because the indexer
already stores every output, a pattern is simply turned into a query over the
existing index.

### GET /matches/{pattern}

Look up outputs matching a watch pattern.

`pattern` is one of:

| Pattern form | Example | Matches |
|--------------|---------|---------|
| `*` | `*` | Every output. |
| Address | `addr_test1...` (bech32) or raw hex | Outputs at exactly that payment address. |
| Stake address | `stake_test1...` (bech32) or raw hex | Outputs whose base address delegates to that stake credential. |
| Policy id | 56 hex characters | Outputs holding any asset of that policy. |
| `policyid.assetname` | `1b3c...058d.000de140436c75623639` | Outputs holding that one specific asset. |

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `spent` | string | `unspent` | Filter by spent-ness: `unspent`, `spent`, or `all`. |

An invalid `spent` value returns `422` with
`{"detail": "spent must be unspent, spent, or all"}`.

Example request (everything, unspent):

```bash
curl "http://127.0.0.1:8000/matches/*"
```

```json
[
  {
    "transaction_id": "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0",
    "output_index": 1,
    "output_reference": "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0#1",
    "address": "addr_test1qrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpszut3w9chzut3w9chzut3w9chzut3w9chzut3w9chzut3wqfcelfw",
    "value": {
      "coins": 250000000,
      "assets": []
    },
    "datum": "",
    "datum_hash": "",
    "spent": false
  },
  {
    "transaction_id": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1",
    "output_index": 0,
    "output_reference": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1#0",
    "address": "addr_test1qzctpv9skzctpv9skzctpv9skzctpv9skzctpv9skzctpvzmtdd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtddslhltfz",
    "value": {
      "coins": 40000000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 400
        }
      ]
    },
    "datum": "d8799f182aff",
    "datum_hash": "fcaa61fb85676101d9e3398a484674e71c45c3fd41b492682f3b0054f4cf3273",
    "spent": false
  },
  {
    "transaction_id": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1",
    "output_index": 1,
    "output_reference": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1#1",
    "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
    "value": {
      "coins": 59500000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 600
        }
      ]
    },
    "datum": "",
    "datum_hash": "",
    "spent": false
  },
  {
    "transaction_id": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02",
    "output_index": 0,
    "output_reference": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02#0",
    "address": "addr_test1qrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpszut3w9chzut3w9chzut3w9chzut3w9chzut3w9chzut3wqfcelfw",
    "value": {
      "coins": 3000000,
      "assets": [
        {
          "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
          "asset_name": "000de140436c75623639",
          "quantity": 1
        }
      ]
    },
    "datum": "",
    "datum_hash": "",
    "spent": false
  },
  {
    "transaction_id": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02",
    "output_index": 1,
    "output_reference": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02#1",
    "address": "addr_test1qrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpszut3w9chzut3w9chzut3w9chzut3w9chzut3w9chzut3wqfcelfw",
    "value": {
      "coins": 3000000,
      "assets": [
        {
          "policy_id": "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
          "asset_name": "000643b0436c75623639",
          "quantity": 1
        }
      ]
    },
    "datum": "d87982a2446e616d6552436c7562203639204d656d6265727368697045696d61676554697066733a2f2f516d436c75623639426164676501",
    "datum_hash": "",
    "spent": false
  }
]
```

Each match is one output, kupo-shaped: `transaction_id` and `output_index`
(combined into `output_reference` as `tx_hash#index`), the `address`, the `value`
(`coins` in lovelace plus any native `assets`), the inline `datum` (CBOR hex, or
`""`), its `datum_hash` (`""` if none), and whether it has been `spent`.

Example request (a single asset pattern, showing the spent filter with `spent=all`):

```bash
curl "http://127.0.0.1:8000/matches/addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu?spent=all"
```

```json
[
  {
    "transaction_id": "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0",
    "output_index": 0,
    "output_reference": "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0#0",
    "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
    "value": {
      "coins": 100000000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 1000
        }
      ]
    },
    "datum": "",
    "datum_hash": "",
    "spent": true
  },
  {
    "transaction_id": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1",
    "output_index": 1,
    "output_reference": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1#1",
    "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
    "value": {
      "coins": 59500000,
      "assets": [
        {
          "policy_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
          "asset_name": "436861696e",
          "quantity": 600
        }
      ]
    },
    "datum": "",
    "datum_hash": "",
    "spent": false
  }
]
```

With `spent=all` both the spent and unspent outputs of the address are returned;
`spent=unspent` (the default) would return only the second, and `spent=spent`
only the first.

### GET /datums/{datum_hash}

Resolve a datum's bytes by its hash.

| Path param | Description |
|------------|-------------|
| `datum_hash` | The datum's blake2b-256 hash (hex). |

Example request:

```bash
curl http://127.0.0.1:8000/datums/fcaa61fb85676101d9e3398a484674e71c45c3fd41b492682f3b0054f4cf3273
```

```json
{
  "datum": "d8799f182aff"
}
```

`datum` is the datum's CBOR bytes as hex. Only datums the indexer has seen inline
have a known preimage; a hash that has only ever appeared by-reference (never with
its bytes) is unknown and returns `404`:

```json
{
  "detail": "datum not found"
}
```

### GET /scripts/{script_hash}

Resolve a reference script by its hash - the language and CBOR of a script attached
to an output (the Conway `referenceScript`, CIP-33). This is kupo's `/scripts`.

| Path param | Description |
|------------|-------------|
| `script_hash` | The script's blake2b-224 hash (hex). |

Example request:

```bash
curl http://127.0.0.1:8000/scripts/bb7d4c3f4a6fa571b8bedd2be462c8661517d5e80dca2589a432be25
```

```json
{
  "script_hash": "bb7d4c3f4a6fa571b8bedd2be462c8661517d5e80dca2589a432be25",
  "type": "plutusV3",
  "cbor": "8203587a587801010029800aba2aba1aab9eaab9dab9a4888896600264646644b30013370e900118031baa002899..."
}
```

`type` is `native`, `plutusV1`, `plutusV2`, or `plutusV3`; `cbor` is the script's
`[language, body]` CBOR as hex. The hash is the ledger's own script hash, so it
matches the script's address. A hash never seen as a reference script returns `404`:

```json
{
  "detail": "script not found"
}
```

Where a hash comes from: every output in `/txs/{hash}` and `/addresses/{addr}`
carries a `reference_script_hash` (and `datum_hash`) when it has one - follow that to
this endpoint.

---

## Pools

### GET /pools

Every stake pool the indexer knows, with summary stats.

Example request:

```bash
curl http://127.0.0.1:8000/pools
```

```json
[
  {
    "pool_id": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
    "blocks_minted": 3,
    "delegators": 2,
    "pledge": 100000000000,
    "margin": 0.03,
    "reward_address": "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75",
    "live_stake": 0.0,
    "saturation": 0.0,
    "cost": 340000000,
    "metadata_url": "https://pool.example/metadata.json",
    "pool_id_hex": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
    "vrf_hash": "abababababababababababababababababababababababababababababababab",
    "metadata_hash": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
    "owners": [
      "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75"
    ],
    "relays": [
      "relay1.pool.example:3001",
      "relay2.pool.example:3001"
    ]
  }
]
```

`pool_id` is the bech32 `pool1...` id (`pool_id_hex` is the same value in hex).
`blocks_minted` and `delegators` come from the indexed chain; `pledge`, `margin`,
`cost`, `reward_address`, `metadata_url`, `vrf_hash`, `metadata_hash`, `owners`
(as stake addresses), and `relays` come from the pool's latest registration.
`live_stake` (fraction of total active stake) and `saturation` need ledger state
and are `0.0` until recorded.

### GET /pools/{pool_id}

Full detail for one pool, including recent blocks, delegators, and per-epoch
performance.

| Path param | Description |
|------------|-------------|
| `pool_id` | The pool id, bech32 (`pool1...`) or hex. |

Example request:

```bash
curl http://127.0.0.1:8000/pools/6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0
```

```json
{
  "pool_id": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
  "blocks_minted": 3,
  "delegators": 2,
  "pledge": 100000000000,
  "margin": 0.03,
  "reward_address": "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75",
  "live_stake": 0.0,
  "saturation": 0.0,
  "cost": 340000000,
  "metadata_url": "https://pool.example/metadata.json",
  "pool_id_hex": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
  "vrf_hash": "abababababababababababababababababababababababababababababababab",
  "metadata_hash": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
  "owners": [
    "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75"
  ],
  "relays": [
    "relay1.pool.example:3001",
    "relay2.pool.example:3001"
  ],
  "recent_blocks": [
    {
      "hash": "c4e1222222222222222222222222222222222222222222222222222222222222",
      "block_no": 3,
      "slot_no": 432010,
      "prev_hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
      "tx_count": 1,
      "tx_hashes": [
        "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02"
      ],
      "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
      "epoch_no": 1,
      "time": "2022-09-06T21:45:01+00:00"
    }
  ],
  "delegators_list": [
    "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75",
    "stake_test1upw9chzut3w9chzut3w9chzut3w9chzut3w9chzut3w9chqth4v8z"
  ],
  "stake_history": [
    { "epoch": 0, "stake": 0.08 },
    { "epoch": 1, "stake": 0.11 }
  ],
  "blocks_by_epoch": [
    { "epoch_no": 0, "block_count": 2 },
    { "epoch_no": 1, "block_count": 1 }
  ],
  "epoch_performance": [
    {
      "epoch_no": 0,
      "stake": 0.08,
      "saturation": 40.0,
      "expected_blocks": 1728.0,
      "made_blocks": 2
    },
    {
      "epoch_no": 1,
      "stake": 0.11,
      "saturation": 55.0,
      "expected_blocks": 2376.0,
      "made_blocks": 1
    }
  ],
  "registered_time": "2022-09-01T21:45:01+00:00",
  "metadata": {
    "name": "Example Stake Pool",
    "ticker": "EXPL",
    "homepage": "https://pool.example",
    "description": "A friendly teaching pool."
  }
}
```

Beyond the summary fields, the detail adds: `recent_blocks` (the shape from
`/blocks`, newest first, shown here trimmed to one entry), `delegators_list` (the
delegating stake addresses), `stake_history` (`{epoch, stake}` where `stake` is
the pool's fraction of active stake), `blocks_by_epoch` (`{epoch_no, block_count}`),
and, when network parameters are configured, `epoch_performance` (per epoch:
`stake`, `saturation` = stake * n_opt, `expected_blocks` from the active-stake
share, and `made_blocks` actually minted) plus `registered_time`. `metadata`
appears only when off-chain metadata fetching is enabled and the fetch succeeds.
Returns `404` with `{"detail": "pool not found"}` for an unknown pool.

---

## Governance

### GET /governance/actions

Every governance action, with its running vote tally.

Example request:

```bash
curl http://127.0.0.1:8000/governance/actions
```

```json
[
  {
    "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#0",
    "action_type": "InfoAction",
    "deposit": 0,
    "tally": {
      "yes": 1,
      "no": 0,
      "abstain": 1
    }
  },
  {
    "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#1",
    "action_type": "ParameterChange",
    "deposit": 100000000000,
    "tally": {
      "yes": 0,
      "no": 0,
      "abstain": 0
    }
  }
]
```

`gov_action_id` is `governance_tx_hash#index`. `action_type` is one of Cardano's
governance action kinds (for example `InfoAction`, `ParameterChange`,
`HardForkInitiation`, `TreasuryWithdrawals`, `NoConfidence`, `NewConstitution`).
`deposit` is the action deposit (lovelace), and `tally` counts the `yes`/`no`/
`abstain` votes cast so far.

### GET /governance/actions/{gov_action_id}

One governance action plus the individual votes cast on it.

| Path param | Description |
|------------|-------------|
| `gov_action_id` | The action id `tx_hash#index`. Percent-encode the `#` as `%23`. |

Example request:

```bash
curl "http://127.0.0.1:8000/governance/actions/1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b%230"
```

```json
{
  "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#0",
  "action_type": "InfoAction",
  "deposit": 0,
  "tally": {
    "yes": 1,
    "no": 0,
    "abstain": 1
  },
  "votes": [
    {
      "voter_role": "DRep",
      "voter_id": "d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1",
      "vote": "Yes",
      "gov_action_id": ""
    },
    {
      "voter_role": "SPO",
      "voter_id": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
      "vote": "Abstain",
      "gov_action_id": ""
    }
  ]
}
```

The same fields as the list, plus `votes`. Each vote has a `voter_role`
(`DRep`, `SPO`, or `ConstitutionalCommittee`), the `voter_id` (the voter's
credential/id), and the `vote` (`Yes`, `No`, or `Abstain`). The nested
`gov_action_id` is `""` here because the action is already known from the path.
Returns `404` with `{"detail": "governance action not found"}` for an unknown id
(also what you get if you forget to encode the `#`).

### GET /governance/protocol-updates

The subset of governance actions that would change protocol parameters or the
protocol version: `ParameterChange` and `HardForkInitiation` actions only.

Example request:

```bash
curl http://127.0.0.1:8000/governance/protocol-updates
```

```json
[
  {
    "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#1",
    "action_type": "ParameterChange",
    "deposit": 100000000000,
    "tally": {
      "yes": 0,
      "no": 0,
      "abstain": 0
    }
  }
]
```

Same per-action shape as `/governance/actions`, filtered to protocol-affecting
kinds (an `InfoAction`, for instance, is excluded).

### GET /governance/dreps

Every delegated representative (DRep), with deposit and vote count.

Example request:

```bash
curl http://127.0.0.1:8000/governance/dreps
```

```json
[
  {
    "drep_id": "d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1",
    "deposit": 500000000,
    "votes_cast": 1
  },
  {
    "drep_id": "d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2",
    "deposit": 500000000,
    "votes_cast": 0
  }
]
```

`drep_id` is the DRep credential, `deposit` its registration deposit (lovelace),
and `votes_cast` how many votes it has cast.

### GET /governance/dreps/{drep_id}

One DRep plus the votes it has cast.

| Path param | Description |
|------------|-------------|
| `drep_id` | The DRep credential/id. |

Example request:

```bash
curl http://127.0.0.1:8000/governance/dreps/d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1
```

```json
{
  "drep_id": "d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1",
  "deposit": 500000000,
  "votes_cast": 1,
  "votes": [
    {
      "gov_action_id": "1ac9d8f5f7b2c0a3e4d6b8c1a2f3049586d7c8b9a0f1e2d3c4b5a69788796a5b#0",
      "action_type": "InfoAction",
      "vote": "Yes"
    }
  ]
}
```

The DRep summary plus `votes`, each linking the `gov_action_id` and its
`action_type` to how the DRep voted (`vote`). `action_type` is `"Unknown"` if the
referenced action has not been indexed. Returns `404` with `{"detail": "DRep not
found"}` for an unknown DRep.

### GET /governance/committee

The constitutional committee members, derived from certificates.

Example request:

```bash
curl http://127.0.0.1:8000/governance/committee
```

```json
[
  {
    "cold_credential": "c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1",
    "hot_credential": "70707070707070707070707070707070707070707070707070707070",
    "resigned": false
  },
  {
    "cold_credential": "c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2",
    "hot_credential": "72727272727272727272727272727272727272727272727272727272",
    "resigned": true
  }
]
```

Each member is keyed by its `cold_credential`; `hot_credential` is the hot key it
authorized to vote on its behalf, and `resigned` is `true` once the member has
resigned its cold credential.

### GET /governance/committee/{cold_credential}

One committee member by cold credential.

| Path param | Description |
|------------|-------------|
| `cold_credential` | The member's cold credential (hex). |

Example request:

```bash
curl http://127.0.0.1:8000/governance/committee/c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1
```

```json
{
  "cold_credential": "c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1",
  "hot_credential": "70707070707070707070707070707070707070707070707070707070",
  "resigned": false
}
```

Same shape as one entry of `/governance/committee`. Returns `404` with
`{"detail": "committee member not found"}` for an unknown credential.

---

## Certificates and withdrawals

### GET /certificates

Certificates indexed from transactions, optionally filtered by category.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `cert_type` | string | (none) | Return only certificates of this category. |

The categories are: `Stake Key Registration`, `Stake Key Deregistration`,
`Delegation`, `Vote Delegation`, `Pool Registration`, `Pool Deregistration`,
`DRep Registration`, `DRep Deregistration`, `DRep Update`,
`Committee Hot Key Authorization`, and `Committee Cold Key Resignation`.

Example request (filtered to stake delegations):

```bash
curl "http://127.0.0.1:8000/certificates?cert_type=Delegation"
```

```json
[
  {
    "cert_type": "Delegation",
    "subject": "5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c5c",
    "subject_display": "stake_test1upw9chzut3w9chzut3w9chzut3w9chzut3w9chzut3w9chqth4v8z",
    "detail": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
    "tx_hash": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02"
  },
  {
    "cert_type": "Delegation",
    "subject": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a",
    "subject_display": "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75",
    "detail": "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0",
    "tx_hash": "9f1e2d3c4b5a69788796a5b4c3d2e1f00112233445566778899aabbccddeeff0"
  }
]
```

Each certificate has a `cert_type` (category label), a `subject` (the primary id
it acts on, in hex), a `subject_display` (a friendlier rendering: `pool1...` for
pools, `stake_test1...` for stake keys, otherwise the hex), a `detail` (a
secondary field whose meaning depends on the category: the pool for a delegation,
`epoch N` for a pool retirement, `deposit N` for a DRep registration, the hot key
for a committee authorization, and so on), and the `tx_hash` it appeared in.
Calling without `cert_type` returns every certificate (all categories), newest
first; an unmatched `cert_type` returns `[]`.

### GET /certificates/summary

A count of indexed certificates per category.

Example request:

```bash
curl http://127.0.0.1:8000/certificates/summary
```

```json
[
  { "cert_type": "Committee Cold Key Resignation", "count": 1 },
  { "cert_type": "Committee Hot Key Authorization", "count": 2 },
  { "cert_type": "DRep Registration", "count": 2 },
  { "cert_type": "DRep Update", "count": 1 },
  { "cert_type": "Delegation", "count": 2 },
  { "cert_type": "Pool Deregistration", "count": 1 },
  { "cert_type": "Pool Registration", "count": 1 },
  { "cert_type": "Stake Key Deregistration", "count": 1 },
  { "cert_type": "Stake Key Registration", "count": 2 },
  { "cert_type": "Vote Delegation", "count": 1 }
]
```

One `{cert_type, count}` entry per category that has at least one certificate.

### GET /withdrawals

Reward-account withdrawals, newest first.

Example request:

```bash
curl http://127.0.0.1:8000/withdrawals
```

```json
[
  {
    "stake_address": "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75",
    "amount": 12500000,
    "tx_hash": "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02"
  }
]
```

Each entry is the reward account (`stake_address`, bech32), the `amount`
withdrawn (lovelace), and the `tx_hash` of the withdrawing transaction.

---

## Analytics and top lists

### GET /analytics/summary

Headline totals across the whole index.

Example request:

```bash
curl http://127.0.0.1:8000/analytics/summary
```

```json
{
  "total_blocks": 3,
  "total_transactions": 3,
  "active_pools": 1,
  "dreps": 2,
  "governance_actions": 2
}
```

Counts of indexed blocks, transactions, pools, DReps, and governance actions.

### GET /analytics/timeseries

Per-epoch totals for charting, newest first. Requires network parameters;
returns `[]` without them.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `limit` | int | 60 | Maximum number of epoch points to return. |

Example request:

```bash
curl http://127.0.0.1:8000/analytics/timeseries
```

```json
[
  {
    "epoch_no": 1,
    "block_count": 1,
    "tx_count": 1,
    "fee_total": 195000,
    "time": "2022-09-06T21:44:51+00:00"
  },
  {
    "epoch_no": 0,
    "block_count": 2,
    "tx_count": 2,
    "fee_total": 360000,
    "time": "2022-09-01T21:44:51+00:00"
  }
]
```

Each point is one epoch: its `block_count`, `tx_count`, total `fee_total`
(lovelace), and the epoch's start `time`.

### GET /top/addresses

The richest payment addresses by unspent balance.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `limit` | int | 20 | Maximum number of addresses to return. |

Example request:

```bash
curl "http://127.0.0.1:8000/top/addresses?limit=5"
```

```json
[
  {
    "address": "addr_test1qrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpsxqcrqvpszut3w9chzut3w9chzut3w9chzut3w9chzut3w9chzut3wqfcelfw",
    "balance": 256000000
  },
  {
    "address": "addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu",
    "balance": 59500000
  },
  {
    "address": "addr_test1qzctpv9skzctpv9skzctpv9skzctpv9skzctpv9skzctpvzmtdd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtddslhltfz",
    "balance": 40000000
  }
]
```

Each entry is an `address` (bech32) and its total unspent `balance` (lovelace).

### GET /top/accounts

The stake accounts controlling the most ada.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `limit` | int | 20 | Maximum number of accounts to return. |

Example request:

```bash
curl http://127.0.0.1:8000/top/accounts
```

```json
[
  {
    "stake_address": "stake_test1upw9chzut3w9chzut3w9chzut3w9chzut3w9chzut3w9chqth4v8z",
    "controlled_stake": 256000000
  },
  {
    "stake_address": "stake_test1upd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95ksyfgt75",
    "controlled_stake": 59500000
  },
  {
    "stake_address": "stake_test1upd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtdd4kk6mtdd4kkc5u2pc5",
    "controlled_stake": 40000000
  }
]
```

Each entry is a `stake_address` (bech32) and the total `controlled_stake`
(lovelace) held by addresses carrying that stake credential.

---

## Epochs

All three epoch endpoints require network parameters. Without them, `/epochs`
returns `[]` and the by-number endpoints return `404` with
`{"detail": "network parameters not configured"}`.

### GET /epochs

Per-epoch summaries, newest first.

Example request:

```bash
curl http://127.0.0.1:8000/epochs
```

```json
[
  {
    "epoch_no": 1,
    "block_count": 1,
    "tx_count": 1,
    "start_slot": 432010,
    "end_slot": 432010,
    "start_time": "2022-09-06T21:44:51+00:00",
    "end_time": "2022-09-06T21:45:01+00:00"
  },
  {
    "epoch_no": 0,
    "block_count": 2,
    "tx_count": 2,
    "start_slot": 10,
    "end_slot": 20,
    "start_time": "2022-09-01T21:44:51+00:00",
    "end_time": "2022-09-01T21:45:11+00:00"
  }
]
```

Each epoch reports its `block_count`, `tx_count`, the `start_slot`/`end_slot` of
the indexed blocks in it, and the corresponding `start_time`/`end_time`.

### GET /epochs/{epoch_no}

One epoch summary.

| Path param | Description |
|------------|-------------|
| `epoch_no` | The epoch number (integer). |

Example request:

```bash
curl http://127.0.0.1:8000/epochs/1
```

```json
{
  "epoch_no": 1,
  "block_count": 1,
  "tx_count": 1,
  "start_slot": 432010,
  "end_slot": 432010,
  "start_time": "2022-09-06T21:44:51+00:00",
  "end_time": "2022-09-06T21:45:01+00:00"
}
```

Same shape as one entry of `/epochs`. Returns `404` with `{"detail": "epoch not
found"}` if the epoch has no indexed blocks.

### GET /epochs/{epoch_no}/blocks

The blocks indexed in one epoch, newest first.

| Path param | Description |
|------------|-------------|
| `epoch_no` | The epoch number (integer). |

Example request:

```bash
curl http://127.0.0.1:8000/epochs/1/blocks
```

```json
[
  {
    "hash": "c4e1222222222222222222222222222222222222222222222222222222222222",
    "block_no": 3,
    "slot_no": 432010,
    "prev_hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
    "tx_count": 1,
    "tx_hashes": [
      "b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff02"
    ],
    "issuer": "pool1dzrksnnq5vdl38w2uk6cx3hnrfw6x0eeda4qpuya4us6q79a7m9",
    "epoch_no": 1,
    "time": "2022-09-06T21:45:01+00:00"
  }
]
```

A list of blocks in the epoch, each with the `/blocks` shape. An epoch with no
indexed blocks returns `[]`.

---

## Mempool

### GET /mempool

A snapshot of the node's mempool (pending, not-yet-indexed transactions). The
mempool is live, so it is queried on demand and is only available when a node
connection is wired in.

Example request:

```bash
curl http://127.0.0.1:8000/mempool
```

```json
{
  "available": true,
  "slot": 432015,
  "capacity": 178176,
  "size_bytes": 4820,
  "tx_count": 2,
  "tx_ids": [
    "e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6",
    "1d2c3b4a5968778695a4b3c2d1e0f9081726354453627180a9b8c7d6e5f40312"
  ]
}
```

`slot` is the slot the snapshot was taken at. `capacity` and `size_bytes` are the
mempool's byte capacity and current fill. `tx_ids` lists the pending transaction
hashes (`tx_count` of them). When no node connection is available (for example in
unit tests), the body is simply `{"available": false}`.

---

## Event sinks (webhooks, log, file)

Sinks are an outbound feature, not a queryable endpoint. As the indexer applies
blocks it publishes small typed events on an internal event bus; a sink subscribes,
keeps only the events matching its filter, and sends each survivor somewhere.
Because rollback (reorg) events flow through the same bus, a sink can react to a
chain reorganization, not just to new blocks. Three sink types ship, all
standard-library only: **webhook** (HTTP POST), **log** (print to the console), and
**file** (append JSON Lines to a file).

### Configuration

Webhooks are configured as a `webhooks` array in the JSON config, each entry a URL
plus optional filter fields:

```json
{
  "webhooks": [
    {
      "url": "https://example.com/hook",
      "addresses": ["addr_test1qzs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rgdp5xs6rg26tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfd95kj6tfdqy6j8pu"]
    },
    {
      "url": "https://example.com/reorgs",
      "types": ["rollback"]
    },
    {
      "url": "https://example.com/nfts",
      "policies": ["1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d"],
      "assets": ["1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d.000de140436c75623639"]
    }
  ]
}
```

The optional filter fields are `types`, `addresses`, `policies`, and `assets`. The
matching semantics are: **OR within a field** (any of the listed addresses match)
and **AND across fields** (an address you want AND a policy you want). A field left
empty does not constrain, so an entry with only a `url` receives every event. An
event that lacks a field the filter constrains on cannot match it (filtering by
address, for instance, selects only the address-bearing `transaction` events).
Configured `addresses` may be bech32 (they are decoded to the raw hex the events
carry); `policies` and `assets` are lower-cased to match.

### The general `sinks` list (log, file, webhook)

The `webhooks` array is shorthand for webhook sinks. The general form is a `sinks`
array, where each entry has a `type` (`webhook`, `log`, or `file`), a `target` where
relevant, and the same optional filter fields:

```json
{
  "sinks": [
    { "type": "log",     "types": ["rollback"] },
    { "type": "file",    "target": "events.jsonl", "policies": ["<policyid>"] },
    { "type": "webhook", "target": "https://example.com/hook", "addresses": ["addr_test1..."] }
  ]
}
```

- **`log`** - prints each matching event as one line of JSON to the console. No
  `target`.
- **`file`** - appends each matching event to the file at `target`, one JSON object
  per line (JSONL): an audit trail you can replay or `grep`.
- **`webhook`** - POSTs to `target` (the URL); identical to a `webhooks` entry.

`type` defaults to `webhook`. Any number of sinks can run at once, each with its own
filter; the `webhooks` and `sinks` lists are both honored.

### Event payloads

The body POSTed is the event object as JSON. The event shapes are:

A `block` event, published once per applied block:

```json
{
  "type": "block",
  "block_no": 2,
  "hash": "7b2c111111111111111111111111111111111111111111111111111111111111",
  "slot": 20,
  "tx_count": 1
}
```

A `transaction` event, published once per transaction, carrying the fields a
webhook filter matches on:

```json
{
  "type": "transaction",
  "tx_hash": "a0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeef1",
  "block_no": 2,
  "addresses": [
    "00b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b05b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b",
    "00a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a15a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a"
  ],
  "policies": [
    "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d",
    "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0"
  ],
  "assets": [
    "1b3c9e5d0f292fcaa02b8b2f9b3c8f9fd8e0bb21abedb692a6d5058d.436861496e644e4654",
    "6887684e60a31bf89dcae5b58346f31a5da33f396f6a00f09daf21a0.436861696e"
  ],
  "lovelace": 99500000,
  "output_count": 2,
  "mint_count": 1
}
```

`addresses` are the transaction's output addresses (raw hex, which is what the
`addresses` filter is matched against). `policies` and `assets` (in the
`policyid.assetname` form the watch patterns use) cover both the outputs and the
mint. `lovelace` is the summed output value, `output_count` the number of outputs,
and `mint_count` the number of assets minted or burned.

A `rollback` event, published when the chain rolls back (a reorg):

```json
{
  "type": "rollback",
  "removed": [
    "c4e1222222222222222222222222222222222222222222222222222222222222",
    "7b2c111111111111111111111111111111111111111111111111111111111111"
  ],
  "count": 2
}
```

`removed` is the list of block hashes that were undone (newest first) and `count`
is their number.

The indexer also publishes a handful of finer-grained domain events on the same
bus (`pool_registered`, `stake_delegated`, `drep_registered`,
`gov_action_proposed`, `vote_cast`). These are not matched by the address/policy/
asset filters (they only carry `type`), but a webhook with `"types": [...]` can
select them.
