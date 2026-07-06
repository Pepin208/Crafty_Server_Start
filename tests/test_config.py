import os
from pydantic import ValidationError
import pytest

from mc_gateway.config import parse_size, Config


def test_parse_size_bytes():
    assert parse_size("10485760", 0) == 10485760
    assert parse_size(10485760, 0) == 10485760


def test_parse_size_units():
    assert parse_size("20MB", 0) == 20 * 1024 * 1024
    assert parse_size("20 MB", 0) == 20 * 1024 * 1024
    assert parse_size("1024KB", 0) == 1024 * 1024
    assert parse_size("1 GB", 0) == 1024 * 1024 * 1024


def test_parse_size_invalid():
    assert parse_size("invalid", 123) == 123
    assert parse_size(None, 456) == 456


def test_config_required_keys(monkeypatch):
    monkeypatch.delenv("CRAFTY_URL", raising=False)
    monkeypatch.delenv("CRAFTY_TOKEN", raising=False)
    monkeypatch.delenv("SERVER_ID", raising=False)
    monkeypatch.delenv("CRAFTY_DIR", raising=False)
    monkeypatch.delenv("MC_PUBLIC_PORT", raising=False)

    with pytest.raises(ValidationError) as exc:
        Config()

    errors = str(exc.value)
    assert "CRAFTY_URL" in errors
    assert "CRAFTY_TOKEN" in errors
    assert "SERVER_ID" in errors
    assert "CRAFTY_DIR" in errors
    assert "MC_PUBLIC_PORT" in errors


def test_config_expansion_and_defaults(monkeypatch, tmp_path):
    mock_dir = tmp_path / "crafty"
    mock_dir.mkdir()

    monkeypatch.setenv("CRAFTY_URL", "http://test")
    monkeypatch.setenv("CRAFTY_TOKEN", "token")
    monkeypatch.setenv("SERVER_ID", "123")
    monkeypatch.setenv("CRAFTY_DIR", str(mock_dir))
    monkeypatch.setenv("MC_PUBLIC_PORT", "25565")

    # Path expansion tests
    monkeypatch.setenv("LOG_FILE", "~/test.log")

    config = Config()

    # Check default parsing
    assert config.MC_INTERNAL_HOST == "127.0.0.1"
    assert config.IDLE_LIMIT_SECONDS == 600

    # Check string size parsing fallback
    assert config.LOG_MAX_BYTES == 10 * 1024 * 1024

    # Check path expansion
    assert config.LOG_FILE == os.path.expanduser("~/test.log")

def test_config_invalid_log_level_fallback(monkeypatch, tmp_path):
    mock_dir = tmp_path / "crafty"
    mock_dir.mkdir()

    monkeypatch.setenv("CRAFTY_URL", "http://test")
    monkeypatch.setenv("CRAFTY_TOKEN", "token")
    monkeypatch.setenv("SERVER_ID", "123")
    monkeypatch.setenv("CRAFTY_DIR", str(mock_dir))
    monkeypatch.setenv("MC_PUBLIC_PORT", "25565")
    monkeypatch.setenv("CRAFTY_LOG_LEVEL", "INVALID_LEVEL")

    config = Config()
    assert config.CRAFTY_LOG_LEVEL == "INFO"
