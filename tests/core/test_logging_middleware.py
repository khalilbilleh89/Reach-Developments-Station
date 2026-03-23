"""
tests.core.test_logging_middleware

Validates the centralized logging and request correlation infrastructure:

  - RequestLoggingMiddleware sets X-Request-ID on every response
  - Log records include request_id, method, path, status, duration_ms
  - _RequestIdFilter injects request_id into all log records automatically
  - _JsonFormatter uses record.created for the timestamp field
  - Unhandled exceptions are logged at ERROR level and re-raised
"""

import json
import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging import _JsonFormatter, _RequestIdFilter, get_logger
from app.core.middleware.request_logging import RequestLoggingMiddleware
from app.core.request_id import generate_request_id, get_request_id, set_request_id


# ---------------------------------------------------------------------------
# Minimal test app
# ---------------------------------------------------------------------------

def _make_test_app() -> FastAPI:
    """Return a minimal FastAPI app with RequestLoggingMiddleware registered."""
    test_app = FastAPI()
    test_app.add_middleware(RequestLoggingMiddleware)

    @test_app.get("/ok")
    async def ok_endpoint():
        return {"status": "ok"}

    @test_app.get("/error")
    async def error_endpoint():
        raise RuntimeError("boom")

    return test_app


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------

class TestRequestLoggingMiddleware:
    def setup_method(self):
        import logging as _logging
        # Re-enable any loggers that an external library (e.g. Alembic via
        # logging.config.fileConfig(disable_existing_loggers=True)) may have
        # disabled before this test runs.
        _logging.getLogger("reach_developments").disabled = False
        _logging.getLogger("reach_developments.request").disabled = False
        self.app = _make_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_x_request_id_header_present_on_success(self):
        response = self.client.get("/ok")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        rid = response.headers["x-request-id"]
        assert rid.startswith("req-")
        # "req-" prefix (4 chars) + 8 hex chars from uuid4().hex[:8]
        assert len(rid) == 12

    def test_x_request_id_header_unique_per_request(self):
        r1 = self.client.get("/ok")
        r2 = self.client.get("/ok")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    def test_log_record_fields_on_success(self, caplog):
        with caplog.at_level(logging.INFO, logger="reach_developments.request"):
            response = self.client.get("/ok")

        assert response.status_code == 200
        request_id = response.headers["x-request-id"]

        # Find the log record emitted by the middleware
        records = [r for r in caplog.records if r.name == "reach_developments.request"]
        assert records, "Expected at least one log record from request middleware"
        record = records[-1]

        assert record.request_id == request_id  # type: ignore[attr-defined]
        assert record.method == "GET"  # type: ignore[attr-defined]
        assert record.path == "/ok"  # type: ignore[attr-defined]
        assert record.status == 200  # type: ignore[attr-defined]
        assert isinstance(record.duration_ms, int)  # type: ignore[attr-defined]
        assert record.duration_ms >= 0  # type: ignore[attr-defined]

    def test_error_path_logs_status_500(self, caplog):
        with caplog.at_level(logging.ERROR, logger="reach_developments.request"):
            response = self.client.get("/error")

        # 500 is returned by TestClient when raise_server_exceptions=False
        assert response.status_code == 500
        records = [r for r in caplog.records if r.name == "reach_developments.request"]
        assert records, "Expected an error log record"
        record = records[-1]
        assert record.levelno == logging.ERROR
        assert record.status == 500  # type: ignore[attr-defined]
        assert record.path == "/error"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _RequestIdFilter tests
# ---------------------------------------------------------------------------

class TestRequestIdFilter:
    def test_filter_injects_request_id_into_record(self):
        # Set a known request ID in the context var
        test_id = generate_request_id()
        set_request_id(test_id)

        lg = get_logger("test.filter")
        filt = _RequestIdFilter()
        record = lg.makeRecord(
            name="test.filter",
            level=logging.INFO,
            fn="<test>",
            lno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.request_id == test_id  # type: ignore[attr-defined]

    def test_filter_returns_empty_string_outside_request(self):
        set_request_id("")
        lg = get_logger("test.filter.empty")
        filt = _RequestIdFilter()
        record = lg.makeRecord(
            name="test.filter.empty",
            level=logging.INFO,
            fn="<test>",
            lno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.request_id == ""  # type: ignore[attr-defined]

    def test_filter_does_not_overwrite_existing_request_id(self):
        """If a caller already set request_id via extra=, the filter must not overwrite it."""
        set_request_id("from-context")
        lg = get_logger("test.filter.no_overwrite")
        filt = _RequestIdFilter()
        record = lg.makeRecord(
            name="test.filter.no_overwrite",
            level=logging.INFO,
            fn="<test>",
            lno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.request_id = "already-set"  # type: ignore[attr-defined]
        filt.filter(record)
        assert record.request_id == "already-set"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _JsonFormatter tests
# ---------------------------------------------------------------------------

class TestJsonFormatter:
    def _make_record(self, msg: str = "test message") -> logging.LogRecord:
        record = logging.LogRecord(
            name="test.json",
            level=logging.INFO,
            pathname="<test>",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        return record

    def test_output_is_valid_json(self):
        formatter = _JsonFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self):
        formatter = _JsonFormatter()
        record = self._make_record("hello world")
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.json"
        assert parsed["message"] == "hello world"
        assert "timestamp" in parsed

    def test_timestamp_derived_from_record_created(self):
        """Timestamp must reflect record.created, not datetime.now()."""
        formatter = _JsonFormatter()
        record = self._make_record()
        # Backdate created by 60 seconds
        record.created = record.created - 60.0
        parsed = json.loads(formatter.format(record))
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(parsed["timestamp"])
        ts_epoch = ts.timestamp()
        # The emitted timestamp should be close to (record.created) not now()
        assert ts_epoch < time.time() - 50, (
            "Timestamp should be ~60s in the past (derived from record.created), "
            f"got {parsed['timestamp']}"
        )

    def test_extra_fields_included(self):
        formatter = _JsonFormatter()
        record = self._make_record()
        record.request_id = "req-abc123"  # type: ignore[attr-defined]
        parsed = json.loads(formatter.format(record))
        assert parsed.get("request_id") == "req-abc123"
