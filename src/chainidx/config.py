"""Central configuration: one place to say what runs and how.

Instead of scattering settings and feature switches across environment variables,
the server reads a single JSON file (like cardano-db-sync's config with its
``insert_options``). It says where the node and database are, which optional
indexers ("features") are on, and whether the opt-in extras (off-chain metadata
fetch, an IPFS gateway, per-epoch stake history) are enabled.

Environment variables still work and take precedence, so existing setups keep
running and a one-off override needs no file. `from_dict` (pure) builds a `Config`
from parsed JSON; `load` reads the file (if any) and layers the environment on top.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

# The optional indexers that can be switched on and off. The core output/input
# indexers are always on (balances depend on them), so they are not listed here.
FEATURES: tuple[str, ...] = ("certificates", "governance", "withdrawals", "assets", "mints")


@dataclass(frozen=True)
class Config:
    """Everything the server needs to know, in one value."""

    socket_path: str = ""
    network_magic: int = 42
    genesis_path: str = ""
    host: str = "127.0.0.1"  # where the explorer/API listens
    port: int = 8000  # change it to run more than one network at once
    db_path: str = "chain.db"
    postgres_dsn: str = ""  # if set, use the Postgres backend instead of SQLite
    fetch_metadata: bool = False
    ipfs_gateway: str = ""
    stake_history: bool = False
    features: frozenset[str] = field(default_factory=lambda: frozenset(FEATURES))
    webhooks: tuple[dict[str, Any], ...] = ()  # webhook sinks, shorthand (chapter 69)
    sinks: tuple[dict[str, Any], ...] = ()  # general event sinks: log/file/webhook (chapter 76)


def from_dict(data: dict[str, object]) -> Config:
    """Build a `Config` from a parsed JSON object, using defaults for what is absent.

    ``features`` is a map of ``{name: on}`` (db-sync style); a feature missing from
    it defaults to on, so an empty or absent map means "everything".
    """
    feats = data.get("features") or {}
    if not isinstance(feats, dict):
        feats = {}
    enabled = frozenset(name for name in FEATURES if feats.get(name, True))
    raw_hooks = data.get("webhooks")
    hooks = (
        tuple(h for h in raw_hooks if isinstance(h, dict)) if isinstance(raw_hooks, list) else ()
    )
    raw_sinks = data.get("sinks")
    sinks = (
        tuple(s for s in raw_sinks if isinstance(s, dict)) if isinstance(raw_sinks, list) else ()
    )
    return Config(
        socket_path=str(data.get("socket_path", "")),
        network_magic=int(str(data.get("network_magic", 42))),
        genesis_path=str(data.get("genesis_path", "")),
        host=str(data.get("host", "127.0.0.1")),
        port=int(str(data.get("port", 8000))),
        db_path=str(data.get("db_path", "chain.db")),
        postgres_dsn=str(data.get("postgres_dsn", "")),
        fetch_metadata=bool(data.get("fetch_metadata", False)),
        ipfs_gateway=str(data.get("ipfs_gateway", "")),
        stake_history=bool(data.get("stake_history", False)),
        features=enabled,
        webhooks=hooks,
        sinks=sinks,
    )


def _with_env(cfg: Config, env: dict[str, str]) -> Config:
    """Layer environment variables over a config; env wins so overrides are easy."""
    magic = env.get("CHAINIDX_MAGIC")
    port = env.get("CHAINIDX_PORT")
    return replace(
        cfg,
        socket_path=env.get("CARDANO_NODE_SOCKET_PATH") or cfg.socket_path,
        network_magic=int(magic) if magic else cfg.network_magic,
        genesis_path=env.get("CHAINIDX_GENESIS") or cfg.genesis_path,
        host=env.get("CHAINIDX_HOST") or cfg.host,
        port=int(port) if port else cfg.port,
        db_path=env.get("CHAINIDX_DB") or cfg.db_path,
        postgres_dsn=env.get("CHAINIDX_POSTGRES_DSN") or cfg.postgres_dsn,
        fetch_metadata=cfg.fetch_metadata or bool(env.get("CHAINIDX_FETCH_METADATA")),
        ipfs_gateway=env.get("CHAINIDX_IPFS_GATEWAY") or cfg.ipfs_gateway,
        stake_history=cfg.stake_history or bool(env.get("CHAINIDX_STAKE_HISTORY")),
    )


def load(path: str | None = None, env: dict[str, str] | None = None) -> Config:
    """Load config from ``path`` (or ``CHAINIDX_CONFIG``), then apply environment."""
    environ = os.environ if env is None else env
    path = path or environ.get("CHAINIDX_CONFIG") or ""
    data: dict[str, object] = {}
    if path:
        with Path(path).open() as handle:
            data = json.load(handle)
    return _with_env(from_dict(data), dict(environ))
