import pytest

import raceindycar.scrape as scrape_mod
from raceindycar.cache import Cache

RECORDS = [
    {"CarNumber": "5", "DriverName": "Pato O'Ward", "TeamName": "Arrow McLaren"},
    {"CarNumber": "12", "DriverName": "Will Power", "TeamName": "Team Penske"},
]


def test_race_record_maps_session_details_fields():
    details = {
        "EventName": "Test GP",
        "SessionDate": "8/16/2026",
        "TrackType": "S",
        "records": [{"LapsComplete": "100"}, {"LapsComplete": "98"}],
    }
    record = scrape_mod.race_record("5520", details)
    assert record["race_id"] == "5520"
    assert record["EventName"] == "Test GP"
    assert record["date"] == "2026-08-16"
    assert record["track_type"] == "S"
    assert record["actual_laps"] == "100"


def test_race_record_handles_no_records():
    record = scrape_mod.race_record("5520", {"EventName": "Test GP"})
    assert record["actual_laps"] == ""


def test_driver_lookup_maps_car_number_to_name_and_team():
    names, teams = scrape_mod.driver_lookup(RECORDS)
    assert names["5"] == "Pato O'Ward"
    assert teams["5"] == "Arrow McLaren"
    assert names["12"] == "Will Power"


def test_build_lap_rows_merges_positions_and_metrics():
    positions = {("5", "1"): 1, ("12", "1"): 2}
    metrics = {
        ("5", "1"): {
            "lap_time": "91.234", "lap_speed": "180.5",
            "on_pit_road": "0", "caution": "1",
        },
    }
    names, teams = scrape_mod.driver_lookup(RECORDS)
    rows = scrape_mod.build_lap_rows(positions, metrics, names, teams)
    by_car = {row["car_number"]: row for row in rows}
    assert by_car["5"]["position"] == 1
    assert by_car["5"]["lap_time"] == "91.234"
    assert by_car["5"]["team"] == "Arrow McLaren"
    assert by_car["5"]["caution"] == "1"
    # car 12 has no PDF metrics entry - fields fall back to empty/default
    assert by_car["12"]["lap_time"] == ""
    assert by_car["12"]["on_pit_road"] == "0"
    assert by_car["12"]["caution"] == "0"


def test_build_lap_rows_uses_metrics_when_no_lap_chart_positions():
    # Practice/Qualifying sessions have no Lap Chart PDF, so `positions` is
    # empty - lap rows must still be built from `metrics` (Section Results).
    positions = {}
    metrics = {
        ("5", "1"): {
            "lap_time": "91.234", "lap_speed": "180.5",
            "on_pit_road": "0", "caution": "0",
        },
        ("5", "2"): {
            "lap_time": "90.111", "lap_speed": "182.0",
            "on_pit_road": "0", "caution": "1",
        },
    }
    names, teams = scrape_mod.driver_lookup(RECORDS)
    rows = scrape_mod.build_lap_rows(positions, metrics, names, teams)
    assert len(rows) == 2
    by_lap = {row["lap_number"]: row for row in rows}
    assert by_lap["1"]["lap_time"] == "91.234"
    assert by_lap["1"]["position"] is None
    assert by_lap["1"]["caution"] == "0"
    assert by_lap["2"]["lap_time"] == "90.111"
    assert by_lap["2"]["caution"] == "1"


def _patch_load_race_deps(monkeypatch, positions_ok, metrics_ok):
    monkeypatch.setattr(scrape_mod, "race_session_id", lambda race_id: "6299")
    monkeypatch.setattr(
        scrape_mod, "session_details", lambda session_id: {"records": RECORDS},
    )
    monkeypatch.setattr(
        scrape_mod,
        "lap_chart_positions",
        lambda race_id, session_id: ({}, positions_ok),
    )
    monkeypatch.setattr(
        scrape_mod, "pdf_metrics", lambda race_id, session_id: ({}, metrics_ok),
    )


def test_load_race_skips_cache_when_pdf_metrics_fail(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    _patch_load_race_deps(monkeypatch, positions_ok=True, metrics_ok=False)
    scrape_mod.load_race("9999")
    assert not (tmp_path / "9999" / "6299" / scrape_mod.SESSION_PICKLE).exists()


def test_load_race_skips_cache_when_lap_chart_fails(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    _patch_load_race_deps(monkeypatch, positions_ok=False, metrics_ok=True)
    scrape_mod.load_race("9997")
    assert not (tmp_path / "9997" / "6299" / scrape_mod.SESSION_PICKLE).exists()


def test_load_race_caches_on_success(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    _patch_load_race_deps(monkeypatch, positions_ok=True, metrics_ok=True)
    scrape_mod.load_race("9998")
    assert (tmp_path / "9998" / "6299" / scrape_mod.SESSION_PICKLE).exists()


def test_load_race_retries_after_failed_attempt(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    _patch_load_race_deps(monkeypatch, positions_ok=True, metrics_ok=False)
    scrape_mod.load_race("9996")
    assert not (tmp_path / "9996" / "6299" / scrape_mod.SESSION_PICKLE).exists()

    _patch_load_race_deps(monkeypatch, positions_ok=True, metrics_ok=True)
    scrape_mod.load_race("9996")
    assert (tmp_path / "9996" / "6299" / scrape_mod.SESSION_PICKLE).exists()


def _write_stub_pdfs(tmp_path, race_id, session_id="6299"):
    session_dir = tmp_path / race_id / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "lapchart.pdf").write_bytes(b"stub")
    (session_dir / "section.pdf").write_bytes(b"stub")
    return session_dir


def test_load_race_discards_pdfs_after_successful_cache(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    session_dir = _write_stub_pdfs(tmp_path, "9995")
    _patch_load_race_deps(monkeypatch, positions_ok=True, metrics_ok=True)
    scrape_mod.load_race("9995")
    assert not (session_dir / "lapchart.pdf").exists()
    assert not (session_dir / "section.pdf").exists()


def test_load_race_keeps_pdfs_when_parse_incomplete(tmp_path, monkeypatch):
    Cache.enable_cache(tmp_path)
    session_dir = _write_stub_pdfs(tmp_path, "9994")
    _patch_load_race_deps(monkeypatch, positions_ok=True, metrics_ok=False)
    scrape_mod.load_race("9994")
    assert (session_dir / "lapchart.pdf").exists()
    assert (session_dir / "section.pdf").exists()


def test_load_race_raises_when_no_session_found(monkeypatch):
    monkeypatch.setattr(scrape_mod, "race_session_id", lambda race_id: None)
    with pytest.raises(ValueError):
        scrape_mod.load_race("no-such-event")
