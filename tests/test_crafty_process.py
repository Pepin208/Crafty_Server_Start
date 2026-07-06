import io
import logging

from mc_gateway.crafty_process import filter_and_log_crafty_output
from mc_gateway.config import config


def test_crafty_log_filter(monkeypatch, caplog):
    monkeypatch.setattr(config, "CRAFTY_LOG_LEVEL", "INFO")

    log_content = b"""[+] Crafty: 06/07/26 18:50:09 - INFO:\tChecking for reset secret flag
Crafty Controller v4.10.4 > [+] Crafty: 06/07/26 18:50:09 - WARNING:\tSome warning
Some ASCII Banner noise
[+] Crafty: 06/07/26 18:50:10 - ERROR:\tFatal error!
"""

    mock_pipe = io.BytesIO(log_content)

    # We use a mocked custom handler so we can inspect output correctly
    class MockHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)

    handler = MockHandler()
    import mc_gateway.crafty_process
    # We must patch the logger inside _get_crafty_logger instead
    def mock_get_logger():
        c_logger = logging.getLogger("crafty_proc_test_1")
        c_logger.setLevel(logging.INFO)
        c_logger.addHandler(handler)
        return c_logger
    monkeypatch.setattr(mc_gateway.crafty_process, "_get_crafty_logger", mock_get_logger)

    filter_and_log_crafty_output(mock_pipe)

    records = handler.records
    assert len(records) == 3
    assert "Checking for reset secret flag" in records[0].message
    assert "Some warning" in records[1].message
    assert "Fatal error!" in records[2].message
    assert "ASCII Banner" not in "\n".join(r.message for r in records)


def test_crafty_log_filter_warning_level(monkeypatch, caplog):
    monkeypatch.setattr(config, "CRAFTY_LOG_LEVEL", "WARNING")

    log_content = b"""[+] Crafty: 06/07/26 18:50:09 - INFO:\tChecking for reset secret flag
[+] Crafty: 06/07/26 18:50:09 - WARNING:\tSome warning
[+] Crafty: 06/07/26 18:50:10 - ERROR:\tFatal error!
"""

    mock_pipe = io.BytesIO(log_content)

    class MockHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)

    handler = MockHandler()
    import mc_gateway.crafty_process
    def mock_get_logger():
        c_logger = logging.getLogger("crafty_proc_test_2")
        c_logger.setLevel(logging.INFO)
        c_logger.addHandler(handler)
        return c_logger
    monkeypatch.setattr(mc_gateway.crafty_process, "_get_crafty_logger", mock_get_logger)

    filter_and_log_crafty_output(mock_pipe)

    records = handler.records
    assert len(records) == 2
    assert "Some warning" in records[0].message
    assert "Fatal error!" in records[1].message
    assert "Checking for reset" not in "\n".join(r.message for r in records)
