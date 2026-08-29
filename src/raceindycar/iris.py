import difflib
import json
from datetime import datetime
from functools import partial

from raceindycar.cache import SCHEDULE_TTL_SECONDS, Cache
from raceindycar.logging import LOGGER

BASE_URL = "https://www.indycar.com"
SERIES_GUID = "b856a4f1-e85c-4fac-8c36-fd58d962227a"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
SESSION_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")
SESSION_ALIASES = {
    "r": "race", "race": "race",
    "w": "warmup", "warmup": "warmup", "warm-up": "warmup",
    "p1": "practice 1", "p2": "practice 2", "p3": "practice 3",
}
SESSION_FUZZY_CUTOFF = 0.6


def session_details(session_id):
    return load_json(
        ("sessions", f"{session_id}.json"),
        None,
        partial(api_get, "/api/results/EventsSessionDetails", {"id": session_id}),
    )


def load_json(parts, ttl, fetcher):
    cached = Cache.path(*parts)
    if Cache.should_read(cached, ttl):
        return json.loads(cached.read_text(encoding="utf-8"))
    payload = fetcher()
    if Cache.should_write():
        Cache.write_text(cached, json.dumps(payload))
    return payload


def api_get(path, params=None):
    response = Cache.requests_get(
        f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=60,
    )
    return response.json()


def season_dropdown():
    return load_json(
        ("season_dropdown.json",),
        SCHEDULE_TTL_SECONDS,
        partial(api_get, "/api/results/SeasonDropDown", {"id": SERIES_GUID}),
    )


def parse_session_date(text):
    raw = str(text or "").strip()
    if not raw:
        return ""
    for fmt in SESSION_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def pick_race_session(sessions):
    try:
        return pick_session(sessions, "race")
    except ValueError:
        return None


def pick_session(sessions, query):
    sessions = sessions or []
    names = [normalize_session_name(s.get("SessionName")) for s in sessions]
    needle = SESSION_ALIASES.get(normalize_session_name(query), normalize_session_name(query))

    for session, name in zip(sessions, names):
        if name == needle:
            return session

    contains = [s for s, name in zip(sessions, names) if needle in name]
    if len(contains) == 1:
        return contains[0]
    if len(contains) > 1:
        options = ", ".join(sorted({s.get("SessionName") for s in contains}))
        raise ValueError(f"'{query}' matched multiple sessions: {options}")

    matches = difflib.get_close_matches(needle, names, n=3, cutoff=SESSION_FUZZY_CUTOFF)
    if len(matches) == 1:
        return sessions[names.index(matches[0])]
    if matches:
        options = ", ".join(s.get("SessionName") for s, name in zip(sessions, names) if name in matches)
        raise ValueError(f"'{query}' matched multiple sessions: {options}")

    available = ", ".join(s.get("SessionName") or "" for s in sessions)
    raise ValueError(f"No session matching '{query}'. Available sessions: {available}")


def normalize_session_name(text):
    return " ".join(str(text or "").strip().lower().split())


def event_sessions(event_id):
    wanted = int(event_id)
    for event in iter_dropdown_events():
        if int(event.get("EventID") or 0) == wanted:
            return event.get("Sessions") or []
    return []


def find_session(event_id, query):
    wanted = int(event_id)
    for event in iter_dropdown_events():
        if int(event.get("EventID") or 0) != wanted:
            continue
        return pick_session(event.get("Sessions") or [], query)
    return None


def iter_dropdown_events():
    for block in season_dropdown():
        yield from block.get("Events") or []


def race_session_id(event_id):
    try:
        return find_session_id(event_id, "race")
    except ValueError:
        return None


def find_session_id(event_id, query):
    session = find_session(event_id, query)
    return session["EventsSessionID"] if session else None


def teams_for_event(race_id):
    try:
        session_id = race_session_id(race_id)
        if not session_id:
            return {}, True
        return teams_from_details(session_details(session_id)), True
    except Exception as exc:
        LOGGER.warning("team lookup failed for %s: %s", race_id, exc)
        return {}, False


def teams_from_details(details):
    teams = {}
    for record in details.get("records") or []:
        if record.get("IsDeleted"):
            continue
        car = normalize_car(record.get("CarNumber"))
        team = str(record.get("TeamName") or "").strip()
        if car and team:
            teams[car] = team
    return teams


def normalize_car(value):
    text = str(value or "").strip()
    return str(int(text)) if text.isdigit() else text
