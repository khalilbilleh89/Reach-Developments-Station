"""A default ledger date must not depend on the host's timezone."""

from datetime import UTC, date, datetime, tzinfo

import pytest

from app.modules.collections.service import _bound, resolve_as_of
from app.modules.inventory import custom_fields


def test_utc_midnight_does_not_hide_a_just_confirmed_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instant = datetime(2026, 9, 7, 0, 30, tzinfo=UTC)

    class HostDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 9, 6)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            assert tz is UTC
            return instant

    monkeypatch.setattr(custom_fields, "date", HostDate)
    monkeypatch.setattr(custom_fields, "datetime", Clock)
    assert resolve_as_of(None) == date(2026, 9, 7)
    assert instant < _bound(resolve_as_of(None))
    # A user-requested historical date is not silently advanced to today.
    assert resolve_as_of(date(2026, 9, 6)) == date(2026, 9, 6)
    assert instant >= _bound(resolve_as_of(date(2026, 9, 6)))
