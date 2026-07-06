import json
import logging
from logging.handlers import RotatingFileHandler
from typing import Any

from mc_gateway.config import config


class JsonFormatter(logging.Formatter):
    """Simple JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


def setup_logger(name: str, config_obj: Any = config) -> logging.Logger:
    """Sets up the main gateway logger based on the current configuration."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicating handlers if setup is called multiple times
    if logger.handlers:
        return logger

    file_handler = RotatingFileHandler(
        config_obj.LOG_FILE,
        maxBytes=int(config_obj.LOG_MAX_BYTES),
        backupCount=config_obj.LOG_BACKUP_COUNT,
    )

    if config_obj.LOG_FORMAT == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if config_obj.LOG_TO_STDOUT:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger

logger = setup_logger("gateway")
