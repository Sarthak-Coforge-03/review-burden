from datetime import datetime, timedelta, timezone

from backend import clock


def test_defaults_to_the_demo_data_as_of(monkeypatch):
    monkeypatch.delenv("AS_OF", raising=False)
    assert clock.now() == datetime(2026, 10, 9, 18, tzinfo=timezone.utc)


def test_wall_uses_the_real_clock(monkeypatch):
    monkeypatch.setenv("AS_OF", " Wall ")
    assert abs(clock.now() - datetime.now(timezone.utc)) < timedelta(seconds=5)


def test_timestamp_without_a_zone_is_read_as_utc(monkeypatch):
    monkeypatch.setenv("AS_OF", "2026-01-02T03:04:05")
    assert clock.now() == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_other_zones_are_converted_to_utc(monkeypatch):
    monkeypatch.setenv("AS_OF", "2026-01-02T03:04:05+05:30")
    result = clock.now()
    assert result == datetime(2026, 1, 1, 21, 34, 5, tzinfo=timezone.utc)
    assert result.tzinfo is timezone.utc
