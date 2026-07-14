"""Tests for the central configuration: JSON plus environment overrides."""

import json
from pathlib import Path

from chainidx import config
from chainidx.indexers import OPTIONAL_INDEXERS, default_indexers, indexers_for


def test_from_dict_defaults_enable_everything() -> None:
    cfg = config.from_dict({})
    assert cfg.db_path == "chain.db"
    assert cfg.network_magic == 42
    assert cfg.fetch_metadata is False
    assert cfg.features == frozenset(config.FEATURES)


def test_from_dict_reads_values_and_feature_toggles() -> None:
    cfg = config.from_dict(
        {
            "socket_path": "/s",
            "network_magic": 1,
            "genesis_path": "/g",
            "db_path": "x.db",
            "fetch_metadata": True,
            "ipfs_gateway": "https://gw/",
            "stake_history": True,
            "features": {"mints": False, "assets": False},
        }
    )
    assert cfg.socket_path == "/s"
    assert cfg.network_magic == 1
    assert cfg.fetch_metadata is True
    assert cfg.ipfs_gateway == "https://gw/"
    assert cfg.stake_history is True
    assert "mints" not in cfg.features
    assert "assets" not in cfg.features
    assert "certificates" in cfg.features  # unspecified features stay on


def test_from_dict_ignores_a_non_object_features_value() -> None:
    assert config.from_dict({"features": "nope"}).features == frozenset(config.FEATURES)


def test_load_layers_env_over_file(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps({"db_path": "file.db", "network_magic": 2, "features": {"mints": False}})
    )
    env = {
        "CHAINIDX_DB": "env.db",
        "CHAINIDX_FETCH_METADATA": "1",
        "CARDANO_NODE_SOCKET_PATH": "/sock",
    }
    cfg = config.load(str(path), env=env)
    assert cfg.db_path == "env.db"  # env wins over the file
    assert cfg.network_magic == 2  # from the file (no env override)
    assert cfg.socket_path == "/sock"
    assert cfg.fetch_metadata is True
    assert "mints" not in cfg.features


def test_load_without_a_file_uses_env_and_defaults() -> None:
    cfg = config.load(env={"CHAINIDX_MAGIC": "7"})
    assert cfg.network_magic == 7
    assert cfg.db_path == "chain.db"


def test_host_and_port_default_and_are_configurable() -> None:
    default = config.from_dict({})
    assert default.host == "127.0.0.1"
    assert default.port == 8000
    cfg = config.from_dict({"host": "0.0.0.0", "port": 9001})
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9001


def test_host_and_port_from_env_win_over_file(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"host": "10.0.0.1", "port": 8080}))
    cfg = config.load(str(path), env={"CHAINIDX_HOST": "0.0.0.0", "CHAINIDX_PORT": "9999"})
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9999


def test_postgres_dsn_from_file_and_env() -> None:
    assert config.from_dict({"postgres_dsn": "dbname=chainidx"}).postgres_dsn == "dbname=chainidx"
    assert config.from_dict({}).postgres_dsn == ""  # SQLite by default
    cfg = config.load(env={"CHAINIDX_POSTGRES_DSN": "dbname=x"})
    assert cfg.postgres_dsn == "dbname=x"


def test_webhooks_parsed_from_config() -> None:
    cfg = config.from_dict({"webhooks": [{"url": "h", "types": ["rollback"]}, "bad"]})
    assert len(cfg.webhooks) == 1  # the non-dict entry is dropped
    assert cfg.webhooks[0]["url"] == "h"
    assert config.from_dict({}).webhooks == ()
    assert config.from_dict({"webhooks": "nope"}).webhooks == ()


def test_indexers_for_selects_optional_features() -> None:
    names = {type(i).__name__ for i in indexers_for(frozenset({"mints"}))}
    assert {"OutputIndexer", "InputIndexer", "MintIndexer"} <= names  # core + mints
    assert "CertIndexer" not in names
    assert len(default_indexers()) == 2 + len(OPTIONAL_INDEXERS)  # all optional on
