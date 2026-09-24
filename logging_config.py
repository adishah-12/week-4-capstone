"""Shared structured logging setup for all agents and both interfaces (CLI, API).

Call setup_logging() once at process start. Every module then just does
    logger = logging.getLogger(__name__)
and logs normally; format and output destinations are controlled centrally here.
"""

import json
import logging
import sys
from pathlib import Path

LOG_FILE = Path(__file__).parent / "app.log"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if setup_logging() is called more than once
    # (e.g. once by the CLI, once by a test importing the same module).
    if root.handlers:
        return

    formatter = JsonFormatter()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
