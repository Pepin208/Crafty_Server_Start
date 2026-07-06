from unittest.mock import MagicMock
from mc_gateway.messages import render_message


def test_render_message_valid():
    mock_config = MagicMock()
    mock_config.IDLE_LIMIT_SECONDS = 300
    mock_config.CRAFTY_IDLE_SECONDS = 600
    mock_config.STARTUP_TIMEOUT_SECONDS = 180

    msg = "Apaga en {idle_min}m, crafty en {crafty_idle_min}m. Timeout: {startup_timeout_seg}s"
    rendered = render_message(msg, mock_config)
    assert rendered == "Apaga en 5.0m, crafty en 10.0m. Timeout: 180s"


def test_render_message_unknown_key():
    mock_config = MagicMock()
    mock_config.IDLE_LIMIT_SECONDS = 300

    msg = "Test {unknown_key} {idle_min}"
    rendered = render_message(msg, mock_config)
    # Should fallback to returning the raw template string on KeyError
    assert rendered == "Test {unknown_key} {idle_min}"
