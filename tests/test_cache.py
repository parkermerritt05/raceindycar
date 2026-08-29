import os
import time

import pytest

import raceindycar.cache as cache_module
from raceindycar.cache import Cache


def test_should_read_missing_file(tmp_path):
    Cache.enable_cache(tmp_path)
    assert Cache.should_read(tmp_path / "missing.json") is False


def test_should_read_empty_file(tmp_path):
    Cache.enable_cache(tmp_path)
    path = tmp_path / "empty.json"
    path.write_text("")
    assert Cache.should_read(path) is False


def test_should_read_fresh_within_ttl(tmp_path):
    Cache.enable_cache(tmp_path)
    path = tmp_path / "fresh.json"
    path.write_text("{}")
    assert Cache.should_read(path, ttl=3600) is True


def test_should_read_stale_past_ttl(tmp_path):
    Cache.enable_cache(tmp_path)
    path = tmp_path / "stale.json"
    path.write_text("{}")
    old = time.time() - 7200
    os.utime(path, (old, old))
    assert Cache.should_read(path, ttl=3600) is False


def test_should_read_no_ttl_ignores_age(tmp_path):
    Cache.enable_cache(tmp_path)
    path = tmp_path / "data.json"
    path.write_text("{}")
    old = time.time() - 10 * 365 * 24 * 60 * 60
    os.utime(path, (old, old))
    assert Cache.should_read(path) is True


def test_should_read_force_renew_bypasses_cache(tmp_path):
    Cache.enable_cache(tmp_path, force_renew=True)
    path = tmp_path / "data.json"
    path.write_text("{}")
    assert Cache.should_read(path) is False


def test_should_read_disabled_bypasses_cache(tmp_path):
    Cache.enable_cache(tmp_path)
    Cache.set_disabled()
    path = tmp_path / "data.json"
    path.write_text("{}")
    assert Cache.should_read(path) is False


def test_disabled_context_manager_restores_previous_state(tmp_path):
    Cache.enable_cache(tmp_path)
    assert Cache.enabled is True
    with Cache.disabled():
        assert Cache.enabled is False
    assert Cache.enabled is True


class _StubResponse:
    def __init__(self, from_cache=False, status_code=200):
        self.from_cache = from_cache
        self.status_code = status_code
        self.reason = ""

    def raise_for_status(self):
        pass


class _StubCache:
    def __init__(self, cached=False):
        self.cached = cached

    def contains(self, url=None):
        return self.cached


class _StubSession:
    """Stands in for requests_cache.CachedSession; isinstance-patched in below."""

    def __init__(self, from_cache=False, cached=False):
        self.from_cache = from_cache
        self.cache = _StubCache(cached)

    def get(self, url, **kwargs):
        return _StubResponse(from_cache=self.from_cache)


def _use_stub_session(monkeypatch, session):
    monkeypatch.setattr(cache_module.requests_cache, "CachedSession", _StubSession)
    monkeypatch.setattr(Cache, "_session_for_request", classmethod(lambda cls: session))


def test_enforce_min_interval_skips_sleep_on_first_request(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    Cache._last_request_time = None
    _use_stub_session(monkeypatch, _StubSession())
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))

    Cache.requests_get("https://example.test/first")

    assert sleeps == []
    assert Cache._last_request_time is not None


def test_enforce_min_interval_sleeps_before_second_request(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    _use_stub_session(monkeypatch, _StubSession())
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr("random.uniform", lambda low, high: 0.0)

    # 3 calls: _enforce_rate_limit's window check, _enforce_min_interval's
    # elapsed-time check (100.5 - 100.0 == 0.5s elapsed), and the
    # post-response bookkeeping that stamps the new _last_request_time.
    clock = iter([100.0, 100.5, 102.0])
    monkeypatch.setattr("time.monotonic", lambda: next(clock))

    Cache._last_request_time = 100.0
    Cache.requests_get("https://example.test/second")

    assert sleeps == [pytest.approx(1.5)]


def test_enforce_min_interval_skipped_on_cache_hit(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    _use_stub_session(monkeypatch, _StubSession(from_cache=True, cached=True))
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))

    Cache._last_request_time = None
    Cache.requests_get("https://example.test/cached")

    assert sleeps == []
    assert Cache._last_request_time is None


def test_enforce_min_interval_skipped_when_offline(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    Cache.offline_mode(True)
    _use_stub_session(monkeypatch, _StubSession(from_cache=True, cached=False))
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))

    Cache._last_request_time = 0.0
    Cache.requests_get("https://example.test/offline")

    assert sleeps == []


def test_enable_cache_defaults_to_pickle_format(tmp_path):
    Cache.enable_cache(tmp_path)
    assert Cache.cache_format == "pickle"


def test_enable_cache_rejects_invalid_cache_format(tmp_path):
    with pytest.raises(ValueError):
        Cache.enable_cache(tmp_path, cache_format="yaml")


PAYLOAD = {
    "race": {"race_id": "5502", "EventName": "Indy 500", "date": "2025-05-25"},
    "drivers": [
        {"CarNumber": "1", "IsDeleted": False, "LapsComplete": "200"},
        {"CarNumber": "0", "IsDeleted": True, "LapsComplete": "5"},
    ],
    "laps": [],
}


def test_save_and_load_payload_pickle_round_trip(tmp_path):
    Cache.enable_cache(tmp_path, cache_format="pickle")
    Cache.save_payload(PAYLOAD, "race123", "sess456", "session.ff1pkl")
    assert (tmp_path / "race123" / "sess456" / "session.ff1pkl").exists()
    assert Cache.load_payload("race123", "sess456", "session.ff1pkl") == PAYLOAD


def test_save_and_load_payload_csv_round_trip(tmp_path):
    Cache.enable_cache(tmp_path, cache_format="csv")
    Cache.save_payload(PAYLOAD, "race123", "sess456", "session.ff1pkl")
    directory = tmp_path / "race123" / "sess456" / "session_csv"
    assert directory.is_dir()
    assert (directory / "drivers.csv").exists()

    loaded = Cache.load_payload("race123", "sess456", "session.ff1pkl")
    assert loaded["race"]["EventName"] == PAYLOAD["race"]["EventName"]
    # numeric-looking text comes back as int/float (CSV has no string/number
    # distinction) - callers normalize these fields with str()/int() anyway.
    assert loaded["race"]["race_id"] == 5502
    # car number "0" must not be lost/blanked, and bools must survive as bools
    car_numbers = {row["CarNumber"] for row in loaded["drivers"]}
    assert car_numbers == {0, 1}
    is_deleted = {row["CarNumber"]: row["IsDeleted"] for row in loaded["drivers"]}
    assert is_deleted[1] is False
    assert is_deleted[0] is True


def test_load_payload_csv_missing_cache_returns_none(tmp_path):
    Cache.enable_cache(tmp_path, cache_format="csv")
    assert Cache.load_payload("nope", "nope", "session.ff1pkl") is None


def test_load_payload_pickle_missing_cache_returns_none(tmp_path):
    Cache.enable_cache(tmp_path, cache_format="pickle")
    assert Cache.load_payload("nope", "nope", "session.ff1pkl") is None
