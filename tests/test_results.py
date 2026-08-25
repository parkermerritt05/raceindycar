from raceindycar.events import Event
from raceindycar.results import build_results, driver_result_row, result_columns

RAW_RECORD = {
    "DriversID": "1234",
    "FirstName": "Test",
    "LastName": "Driver",
    "DriverName": "Test Driver",
    "CarNumber": "9",
    "PositionStart": "5",
    "PositionFinish": "1",
    "Status": "Running",
    "PointsEarned": "50",
    "LapsComplete": "100",
    "LapsLed": "10",
    "TimesLed": "1",
    "PitStops": "2",
    "BestSpeed": "200.5",
    "SpeedAvg": "195.2",
    "TeamName": "",
    "IsDeleted": False,
}


def make_event():
    return Event({
        "race_id": "5452", "EventName": "Test GP", "date": "2024-06-02",
        "track_type": "Street circuit", "actual_laps": "100",
    })


def test_driver_result_row_maps_iris_fields():
    row = driver_result_row(RAW_RECORD, make_event(), teams={})
    assert row["DriverId"] == "1234"
    assert row["FirstName"] == "Test"
    assert row["LastName"] == "Driver"
    assert row["FullName"] == "Test Driver"
    assert row["Abbreviation"] == "DRI"
    assert row["DriverNumber"] == "9"
    assert row["GridPosition"] == 5
    assert row["Position"] == 1
    assert row["FastestLapSpeed"] == 200.5
    assert row["AvgLapSpeed"] == 195.2


def test_driver_result_row_falls_back_to_team_lookup():
    row = driver_result_row(RAW_RECORD, make_event(), teams={"9": "Fallback Racing"})
    assert row["Team"] == "Fallback Racing"


def test_result_columns_no_longer_include_lapraptor_only_fields():
    columns = result_columns()
    for name in ("DriverId", "FirstName", "LastName", "FullName", "Abbreviation"):
        assert name in columns
    for name in ("GrLr", "Rr", "Pgae"):
        assert name not in columns


def test_build_results_frame_exposes_mapped_fields():
    frame = build_results([RAW_RECORD], make_event(), laps=None)
    assert frame.iloc[0]["DriverId"] == "1234"
    assert frame.iloc[0]["Position"] == 1


def test_build_results_skips_deleted_records():
    deleted = dict(RAW_RECORD, IsDeleted=True)
    frame = build_results([RAW_RECORD, deleted], make_event(), laps=None)
    assert len(frame) == 1
