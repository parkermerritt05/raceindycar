import pytest

from raceindycar import iris

SESSIONS = [
    {"SessionName": "Practice 1", "EventsSessionID": 1},
    {"SessionName": "Practice 2", "EventsSessionID": 2},
    {"SessionName": "Qualifying - Round 1 Group 1", "EventsSessionID": 3},
    {"SessionName": "Qualifying - Round 1 Group 2", "EventsSessionID": 4},
    {"SessionName": "Qualifying - Round 2", "EventsSessionID": 5},
    {"SessionName": "Qualifying - Firestone Fast 6", "EventsSessionID": 6},
    {"SessionName": "Warmup", "EventsSessionID": 7},
    {"SessionName": "Race", "EventsSessionID": 8},
]


def test_pick_session_matches_alias_short_code():
    assert iris.pick_session(SESSIONS, "P1")["EventsSessionID"] == 1
    assert iris.pick_session(SESSIONS, "r")["EventsSessionID"] == 8
    assert iris.pick_session(SESSIONS, "Warmup")["EventsSessionID"] == 7


def test_pick_session_matches_substring():
    assert iris.pick_session(SESSIONS, "Firestone Fast 6")["EventsSessionID"] == 6
    assert iris.pick_session(SESSIONS, "Round 2")["EventsSessionID"] == 5
    assert iris.pick_session(SESSIONS, "Round 1 Group 2")["EventsSessionID"] == 4


def test_pick_session_ambiguous_substring_raises_with_options():
    with pytest.raises(ValueError, match="Round 1 Group 1.*Round 1 Group 2|Round 1 Group 2.*Round 1 Group 1"):
        iris.pick_session(SESSIONS, "Round 1")


def test_pick_session_ambiguous_qualifying_alias_raises():
    with pytest.raises(ValueError):
        iris.pick_session(SESSIONS, "Q")


def test_pick_session_no_match_raises_listing_available():
    with pytest.raises(ValueError, match="Practice 1"):
        iris.pick_session(SESSIONS, "Sprint")


def test_pick_race_session_returns_none_when_absent():
    assert iris.pick_race_session([{"SessionName": "Practice 1"}]) is None
