import time
from datetime import date, datetime

from raceindycar.iris import season_dropdown, session_details, year_winners
from raceindycar.logging import LOGGER

MIN_YEAR = 1996
REQUEST_DELAY_SECONDS = 0.25
RACE_SESSION_TYPE = "R"
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")
SKIP_NAME_FRAGMENTS = (
    "practice", "qualif", "warmup", "warm-up", "heat", "all star",
)
SESSION_SURFACE = {"R": "road", "O": "oval", "I": "oval"}
WINNER_SURFACE = {
    "Oval": "oval", "Road Course": "road", "Street Course": "street",
}
FIELDS = [
    "Season", "Race", "Track", "Name", "Date", "Surface",
    "Finish", "Start", "Car", "Driver", "Team",
    "Pts", "Laps", "Led", "Status", "Win",
]


def historical_rows(min_year=MIN_YEAR, delay=REQUEST_DELAY_SECONDS):
    dropdown = season_dropdown()
    rows, failed = collect_rows(dropdown, min_year, delay)
    return sort_rows(rows), failed


def collect_rows(dropdown, min_year, delay=REQUEST_DELAY_SECONDS):
    rows, failed = [], []
    for year, events in events_by_year(dropdown, min_year):
        try:
            races = fetch_year_races(year, events, delay)
            year_rows = rows_for_year(races)
            rows.extend(year_rows)
            LOGGER.info("%s: %s races, %s starters", year, len(races), len(year_rows))
        except Exception as exc:
            failed.append((year, str(exc)))
            LOGGER.warning("%s: failed (%s)", year, exc)
        time.sleep(delay)
    return rows, failed


def events_by_year(dropdown, min_year):
    blocks = []
    for block in dropdown:
        year = int(block["Year"])
        if year >= min_year:
            blocks.append((year, block.get("Events") or []))
    return sorted(blocks, key=lambda item: item[0])


def fetch_year_races(year, events, delay=REQUEST_DELAY_SECONDS):
    races = []
    for event in events:
        for session in pick_race_sessions(event):
            details = session_details(session["EventsSessionID"])
            time.sleep(delay)
            if details.get("SessionType") != RACE_SESSION_TYPE:
                continue
            if not details.get("records"):
                continue
            races.append(race_record(year, event, details))
    return attach_tracks(races, year_winners(year))


def pick_race_sessions(event):
    sessions = event.get("Sessions") or []
    exact = [
        session for session in sessions
        if (session.get("SessionName") or "").strip().lower() == "race"
    ]
    if exact:
        return exact
    fallback = [
        session for session in sessions
        if not is_skipped_name(session.get("SessionName"))
    ]
    return fallback[:1]


def is_skipped_name(name):
    lower = (name or "").lower()
    return any(fragment in lower for fragment in SKIP_NAME_FRAGMENTS)


def race_record(year, event, details):
    return {
        "year": int(year),
        "event_id": int(event["EventID"]),
        "name": clean_text(details.get("EventName") or event.get("EventName")),
        "date": iso_date(parse_date(details.get("SessionDate"))),
        "track": "",
        "surface": SESSION_SURFACE.get((details.get("TrackType") or "").strip(), ""),
        "records": details.get("records") or [],
    }


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def parse_date(text):
    if not text:
        return None
    raw = str(text).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def iso_date(day):
    return day.isoformat() if day else ""


def attach_tracks(races, winners):
    ordered = sorted(
        races,
        key=lambda race: (race["date"] or "9999", race["event_id"]),
    )
    unused = sorted(winners or [], key=winner_day)
    if len(ordered) == len(unused):
        for race, winner in zip(ordered, unused):
            apply_winner(race, winner)
        return ordered
    for race in ordered:
        winner = pop_closest_winner(parse_date(race["date"]), unused)
        apply_winner(race, winner)
    return ordered


def winner_day(winner):
    return parse_date(winner.get("RaceDate")) or date.max


def apply_winner(race, winner):
    if not winner:
        return
    race["track"] = clean_text(winner.get("TrackName"))
    mapped = WINNER_SURFACE.get(winner.get("TrackType") or "", "")
    race["surface"] = mapped or race["surface"]


def pop_closest_winner(race_day, unused):
    if not unused:
        return None
    if race_day is None:
        return unused.pop(0)
    index = min(
        range(len(unused)),
        key=lambda i: abs((winner_day(unused[i]) - race_day).days),
    )
    return unused.pop(index)


def rows_for_year(races):
    rows = []
    for round_number, race in enumerate(races, start=1):
        starters = [item for item in race["records"] if not item.get("IsDeleted")]
        rows.extend(result_row(race, item, round_number) for item in starters)
    return rows


def result_row(race, record, round_number):
    finish = clean_int(record.get("PositionFinish"))
    return {
        "Season": race["year"],
        "Race": round_number,
        "Track": race["track"],
        "Name": race["name"],
        "Date": race["date"],
        "Surface": race["surface"],
        "Finish": finish,
        "Start": clean_int(record.get("PositionStart")),
        "Car": clean_text(record.get("CarNumber")),
        "Driver": clean_text(record.get("DriverName")),
        "Team": clean_text(record.get("TeamName")),
        "Pts": clean_int(record.get("PointsEarned")),
        "Laps": clean_int(record.get("LapsComplete")),
        "Led": clean_int(record.get("LapsLed")),
        "Status": clean_text(record.get("Status")),
        "Win": int(finish == 1),
    }


def clean_int(value):
    if value is None or value == "":
        return ""
    try:
        return int(value)
    except (TypeError, ValueError):
        return ""


def sort_rows(rows):
    return sorted(
        rows,
        key=lambda row: (
            row["Season"],
            row["Race"],
            row["Finish"] if row["Finish"] != "" else 999,
        ),
    )
