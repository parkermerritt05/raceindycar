import difflib
import re

import pandas as pd

from raceindycar.iris import (
    event_sessions,
    find_session,
    pick_race_session,
    season_dropdown,
)
from raceindycar.laps import build_laps
from raceindycar.results import build_results
from raceindycar.scrape import load_race

SERIES_PREFIX_RE = re.compile(
    r"^\d{4}\s+(?:ntt\s+)?(?:indycar\s+series\s+)?", re.I,
)
ORDINAL_RUNNING_PREFIX_RE = re.compile(
    r"^\d+(?:st|nd|rd|th)\s+running\s+of\s+the\s+", re.I,
)
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
RACE_ID_MIN = 1000
FUZZY_CUTOFF = 0.6


def get_event_schedule(year):
    dropdown = season_dropdown()
    block = next((b for b in dropdown if int(b["Year"]) == int(year)), None)
    events = reversed((block or {}).get("Events") or [])
    rows = [row for row in (schedule_row(year, e) for e in events) if row]
    for round_number, row in enumerate(rows, start=1):
        row["round_number"] = round_number
    return EventSchedule(rows)


def schedule_row(year, event):
    if not pick_race_session(event.get("Sessions") or []):
        return None
    return {
        "year": int(year),
        "race_id": str(event["EventID"]),
        "EventName": event.get("EventName") or "",
    }


def get_event(year, race):
    return Event(resolve_event_row(year, race).to_dict())


def resolve_event_row(year, race):
    schedule = get_event_schedule(year)
    if schedule.empty:
        raise ValueError(f"No IndyCar races found for {year}")
    if is_race_id(race):
        hits = schedule[schedule["race_id"] == str(int(race))]
        if hits.empty:
            raise ValueError(f"No IndyCar race {race} in {year}")
        return hits.iloc[0]
    if is_round_number(race):
        round_num = int(race)
        hits = schedule[schedule["round_number"] == round_num]
        if not hits.empty:
            return hits.iloc[0]
        raise ValueError(
            f"Round {round_num} does not exist for {year} "
            f"(season has {len(schedule)} races)"
        )
    return match_event(schedule, race)


def is_race_id(value):
    text = str(value).strip()
    return text.isdigit() and int(text) >= RACE_ID_MIN


def is_round_number(value):
    text = str(value).strip()
    return text.isdigit() and not is_race_id(value)


def match_event(schedule, query):
    needle = normalize_race_name(query)
    names = schedule["EventName"].map(normalize_race_name)
    matched = unique_match(schedule, names == needle, query)
    if matched is not None:
        return matched
    contains = names.str.contains(re.escape(needle), regex=True)
    matched = unique_match(schedule, contains, query)
    if matched is not None:
        return matched
    return closest_event(schedule, names, needle, query)


def normalize_race_name(name):
    text = SERIES_PREFIX_RE.sub("", str(name or ""))
    text = ORDINAL_RUNNING_PREFIX_RE.sub("", text)
    text = NON_ALNUM_RE.sub(" ", text.casefold())
    return " ".join(text.split())


def unique_match(schedule, mask, query):
    hits = schedule[mask]
    if len(hits) == 1:
        return hits.iloc[0]
    if len(hits) > 1:
        raise_ambiguous(query, hits)
    return None


def raise_ambiguous(query, hits):
    listed = "\n".join(
        f"  {race_id} {name}"
        for race_id, name in zip(hits["race_id"], hits["EventName"])
    )
    raise ValueError(f"'{query}' matched multiple races:\n{listed}")


def closest_event(schedule, names, needle, query):
    matches = difflib.get_close_matches(
        needle, names.tolist(), n=3, cutoff=FUZZY_CUTOFF,
    )
    if len(matches) == 1:
        return schedule[names == matches[0]].iloc[0]
    if matches:
        raise_ambiguous(query, schedule[names.isin(matches)])
    raise ValueError(f"No IndyCar race matching '{query}'")


class EventSchedule(pd.DataFrame):
    @property
    def _constructor(self):
        return EventSchedule

    def get_event_by_name(self, name):
        return Event(match_event(self, name).to_dict())


class Event:
    def __init__(self, data):
        for key, value in data.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __repr__(self):
        fields = ", ".join(f"{key}={value!r}" for key, value in vars(self).items())
        return f"Event({fields})"

    @property
    def sessions(self):
        return event_sessions(self.race_id)

    def get_session(self, session="R"):
        session_row = find_session(self.race_id, session)
        if session_row is None:
            raise ValueError(f"No '{session}' session found for {self.EventName}")
        return Session(
            event=self,
            session=session,
            session_id=session_row["EventsSessionID"],
            name=session_row.get("SessionName"),
        )


def get_session(year, race, session="R"):
    return get_event(year, race).get_session(session)


def lookup_driver(results, identifier):
    text = str(identifier).strip()
    if text.isdigit():
        hits = results[results["DriverNumber"] == str(int(text))]
    else:
        hits = results[results["Abbreviation"] == text.upper()]
        if hits.empty:
            names = results["FullName"].astype(str).str.casefold()
            hits = results[names == text.casefold()]
    if hits.empty:
        raise KeyError(identifier)
    return hits.iloc[0]


class Session:
    def __init__(self, event, session, session_id, name):
        self.event = event
        self.year = event.year
        self.session = session
        self.name = name
        self.date = getattr(event, "date", None)
        self._race_id = event.race_id
        self._session_id = session_id
        self.results = None
        self.laps = None

    def __repr__(self):
        return (
            f"Session(event={self.event!r}, session={self.session!r}, "
            f"name={self.name!r}, date={self.date!r}, year={self.year!r})"
        )

    def load(self):
        payload = load_race(self._race_id, self._session_id)
        self.event = Event(payload["race"])
        self.event.year = self.year
        self.date = self.event.date
        self.laps = build_laps(payload["laps"])
        self.results = build_results(payload["drivers"], self.event, self.laps)
        return self

    def get_driver(self, identifier):
        if self.results is None:
            raise RuntimeError("Call load() before get_driver()")
        return lookup_driver(self.results, identifier)
