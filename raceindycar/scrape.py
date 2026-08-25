from raceindycar.cache import Cache
from raceindycar.iris import parse_session_date, race_session_id, session_details
from raceindycar.logging import LOGGER
from raceindycar.pdf_fetch import lap_chart_positions, pdf_metrics

SESSION_PICKLE = "session.ff1pkl"


def normalize_car(value):
    text = str(value or "").strip()
    return str(int(text)) if text.isdigit() else text


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def race_record(race_id, details):
    laps_complete = [to_int(r.get("LapsComplete")) for r in details.get("records") or []]
    return {
        "race_id": str(race_id),
        "EventName": details.get("EventName", ""),
        "date": parse_session_date(details.get("SessionDate")),
        "track_type": details.get("TrackType", ""),
        "actual_laps": str(max(laps_complete)) if laps_complete else "",
    }


def driver_lookup(records):
    names, teams = {}, {}
    for record in records:
        car = normalize_car(record.get("CarNumber"))
        names[car] = record.get("DriverName", "")
        teams[car] = record.get("TeamName", "")
    return names, teams


def build_lap_rows(positions, metrics, names, teams):
    rows = []
    for car, lap in sorted(set(positions) | set(metrics)):
        extra = metrics.get((car, lap), {})
        rows.append({
            "driver_name": names.get(car, ""),
            "car_number": car,
            "lap_number": lap,
            "position": positions.get((car, lap)),
            "lap_speed": extra.get("lap_speed", ""),
            "lap_time": extra.get("lap_time", ""),
            "on_pit_road": extra.get("on_pit_road", "0"),
            "team": teams.get(car, ""),
        })
    return rows


def load_race(race_id, session_id=None):
    if session_id is None:
        session_id = race_session_id(race_id)
    if not session_id:
        raise ValueError(f"No race session found for event {race_id}")

    parsed = Cache.load_pickle(str(race_id), str(session_id), SESSION_PICKLE)
    if parsed is not None:
        LOGGER.debug("pickle hit %s/%s", race_id, session_id)
        return parsed

    details = session_details(session_id)
    records = details.get("records") or []

    positions, positions_ok = lap_chart_positions(race_id, session_id)
    metrics, metrics_ok = pdf_metrics(race_id, session_id)
    names, teams = driver_lookup(records)

    if not positions and not metrics:
        LOGGER.warning("no lap data (positions or metrics) for %s/%s", race_id, session_id)

    payload = {
        "race": race_record(race_id, details),
        "drivers": records,
        "laps": build_lap_rows(positions, metrics, names, teams),
        "cautions": [],
    }
    if positions_ok and metrics_ok:
        Cache.save_pickle(payload, str(race_id), str(session_id), SESSION_PICKLE)
    return payload
