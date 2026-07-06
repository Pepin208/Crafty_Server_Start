
from mc_gateway.config_hotswap import reload_hotswap_config
from mc_gateway.config import config


def test_hotswap_with_toml(monkeypatch, tmp_path):
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('IDLE_LIMIT_SECONDS = 999\nCRAFTY_LOG_LEVEL = "WARNING"')

    # Mock working directory to our tmp_path to find the config.toml
    monkeypatch.chdir(tmp_path)

    # Set current config
    config.IDLE_LIMIT_SECONDS = 100
    config.CRAFTY_LOG_LEVEL = "INFO"
    # Unchanged value
    config.CHECK_INTERVAL_SECONDS = 50

    # We must patch load_config to read from our tmp file
    def mock_load_config():
        from mc_gateway.config import Config
        return Config(
            CRAFTY_URL="http", CRAFTY_TOKEN="t", SERVER_ID="1", CRAFTY_DIR="d", MC_PUBLIC_PORT=1,
        )

    monkeypatch.setattr("mc_gateway.config_hotswap.load_config", mock_load_config)

    reload_hotswap_config()

    assert config.IDLE_LIMIT_SECONDS == 999
    assert config.CRAFTY_LOG_LEVEL == "WARNING"
    assert config.CHECK_INTERVAL_SECONDS == 20  # Default loaded by Config since not in TOML


def test_hotswap_without_toml(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    config.IDLE_LIMIT_SECONDS = 100

    reload_hotswap_config()

    # Should not change because there's no config.toml
    assert config.IDLE_LIMIT_SECONDS == 100
