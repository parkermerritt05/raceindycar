from raceindycar.history import (
    attach_tracks,
    events_by_year,
    pop_closest_winner,
    result_row,
)


def test_pop_closest_winner_picks_nearest_date():
    import datetime

    unused = [
        {"RaceDate": "2024-01-01", "TrackName": "Far Track", "TrackType": "Oval"},
        {"RaceDate": "2024-06-01", "TrackName": "Near Track", "TrackType": "Road Course"},
    ]
    winner = pop_closest_winner(datetime.date(2024, 6, 2), unused)
    assert winner["TrackName"] == "Near Track"
    assert len(unused) == 1


def test_pop_closest_winner_empty_returns_none():
    assert pop_closest_winner(None, []) is None


def test_attach_tracks_equal_length_zips_in_date_order():
    races = [
        {"event_id": 2, "date": "2024-06-01", "track": "", "surface": ""},
        {"event_id": 1, "date": "2024-01-01", "track": "", "surface": ""},
    ]
    winners = [
        {"RaceDate": "2024-01-01", "TrackName": "Early Track", "TrackType": "Oval"},
        {"RaceDate": "2024-06-01", "TrackName": "Late Track", "TrackType": "Street Course"},
    ]
    ordered = attach_tracks(races, winners)
    assert ordered[0]["track"] == "Early Track"
    assert ordered[0]["surface"] == "oval"
    assert ordered[1]["track"] == "Late Track"
    assert ordered[1]["surface"] == "street"


def test_attach_tracks_unequal_length_uses_closest_match():
    races = [
        {"event_id": 1, "date": "2024-01-01", "track": "", "surface": "road"},
        {"event_id": 2, "date": "2024-06-01", "track": "", "surface": "road"},
    ]
    winners = [
        {"RaceDate": "2024-01-02", "TrackName": "Only Winner", "TrackType": "Oval"},
    ]
    ordered = attach_tracks(races, winners)
    assert ordered[0]["track"] == "Only Winner"
    assert ordered[1]["track"] == ""
    assert ordered[1]["surface"] == "road"


def test_result_row_maps_fields_and_detects_win():
    race = {
        "year": 2024, "track": "Test Track", "name": "Test GP",
        "date": "2024-06-02", "surface": "street",
    }
    record = {
        "PositionFinish": "1", "PositionStart": "5", "CarNumber": "9",
        "DriverName": "Test Driver", "TeamName": "Test Team",
        "PointsEarned": "53", "LapsComplete": "100", "LapsLed": "35",
        "Status": "Running",
    }
    row = result_row(race, record, round_number=3)
    assert row["Season"] == 2024
    assert row["Race"] == 3
    assert row["Finish"] == 1
    assert row["Start"] == 5
    assert row["Win"] == 1


def test_result_row_non_winner_has_win_zero():
    race = {"year": 2024, "track": "", "name": "", "date": "", "surface": ""}
    record = {"PositionFinish": "2"}
    row = result_row(race, record, round_number=1)
    assert row["Win"] == 0


def test_events_by_year_filters_and_sorts():
    dropdown = [
        {"Year": "2022", "Events": ["b"]},
        {"Year": "2020", "Events": ["a"]},
        {"Year": "2019", "Events": ["skip"]},
    ]
    result = events_by_year(dropdown, min_year=2020)
    assert [year for year, _ in result] == [2020, 2022]
