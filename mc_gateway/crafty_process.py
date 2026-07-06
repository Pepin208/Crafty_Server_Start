import logging
import os
import re
import subprocess
import threading
import time
from logging.handlers import RotatingFileHandler
from typing import IO

from mc_gateway.config import config
from mc_gateway.logging_setup import logger

_WARNING_OR_WORSE = {"WARNING", "WARN", "ERROR", "CRITICAL", "FATAL"}
_CRAFTY_LINE_RE = re.compile(r"\[\+\]\s*Crafty:\s*\d{2}/\d{2}/\d{2}\s*-?\s*\d{2}:\d{2}:\d{2}\s*-\s*(\w+):")


def _get_crafty_logger() -> logging.Logger:
    c_logger = logging.getLogger("crafty_proc")
    if c_logger.handlers:
        return c_logger
    c_logger.setLevel(logging.INFO)
    c_logger.propagate = False
    handler = RotatingFileHandler(
        config.CRAFTY_LOG_FILE,
        maxBytes=int(config.CRAFTY_LOG_MAX_BYTES),
        backupCount=config.CRAFTY_LOG_BACKUP_COUNT,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    c_logger.addHandler(handler)
    return c_logger


def filter_and_log_crafty_output(pipe: IO[bytes]) -> None:
    """Reads Crafty process output, filters noise, and writes to log."""
    c_logger = _get_crafty_logger()
    try:
        for raw_line in iter(pipe.readline, b""):
            try:
                line = raw_line.decode(errors="replace").rstrip("\n")
            except Exception:
                line = str(raw_line)
            stripped = line.strip()
            if not stripped:
                continue

            idx = stripped.find("[+] Crafty:")
            if idx != -1:
                stripped = stripped[idx:]

            match = _CRAFTY_LINE_RE.match(stripped)
            if not match:
                continue

            if config.CRAFTY_LOG_LEVEL == "WARNING" and match.group(1).upper() not in _WARNING_OR_WORSE:
                continue

            c_logger.info(stripped)
    finally:
        pipe.close()


class CraftyProcessManager:
    def __init__(self):
        self.crafty_pid: int | None = None

    def start_crafty(self) -> bool:
        from mc_gateway.crafty_client import is_crafty_up

        logger.info("Levantando Crafty Controller...")
        proc = subprocess.Popen(
            ["bash", "-c", "source venv/bin/activate && exec python3 main.py"],
            cwd=config.CRAFTY_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.crafty_pid = proc.pid
        if proc.stdout is not None:
            threading.Thread(target=filter_and_log_crafty_output, args=(proc.stdout,), daemon=True).start()

        for _ in range(30):
            if is_crafty_up():
                logger.info("Crafty está up.")
                return True
            time.sleep(2)

        logger.error("ERROR: Crafty no levantó a tiempo.")
        return False

    def stop_crafty(self) -> None:
        if self.crafty_pid:
            logger.info(f"Apagando Crafty (pid {self.crafty_pid})...")
            try:
                os.kill(self.crafty_pid, 15)
            except ProcessLookupError:
                pass
            self.crafty_pid = None
        else:
            subprocess.run(["pkill", "-f", f"{config.CRAFTY_DIR}/main.py"])


crafty_process_manager = CraftyProcessManager()
