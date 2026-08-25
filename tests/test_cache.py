import os
import time

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
