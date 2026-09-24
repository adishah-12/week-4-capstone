"""Tests for the shared structured logging setup."""

import json
import logging

from logging_config import JsonFormatter, setup_logging


class TestJsonFormatter:
    def test_produces_valid_json_with_expected_fields(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger", level=logging.INFO, pathname="x.py", lineno=1,
            msg="hello %s", args=("world",), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "hello world"
        assert "timestamp" in parsed
        assert "exception" not in parsed

    def test_includes_exception_field_when_exc_info_present(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test.logger", level=logging.ERROR, pathname="x.py", lineno=1,
                msg="failed", args=(), exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError: boom" in parsed["exception"]


class TestSetupLogging:
    def test_adds_handlers_to_root_logger(self):
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        try:
            root.handlers = []
            setup_logging()
            assert len(root.handlers) == 2
        finally:
            root.handlers = original_handlers

    def test_calling_twice_does_not_duplicate_handlers(self):
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        try:
            root.handlers = []
            setup_logging()
            setup_logging()
            assert len(root.handlers) == 2
        finally:
            root.handlers = original_handlers
