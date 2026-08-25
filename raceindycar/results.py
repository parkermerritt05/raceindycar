import pandas as pd

ABBREV_LEN = 3
RACE_COLUMNS = {
    "race_id": "RaceId",
    "EventName": "RaceName",
    "date": "Date",
    "track_type": "TrackType",
    "actual_laps": "ActualLaps",
}


def build_results(records, event, laps=None):
    teams = team_by_car(laps)
    active = [record for record in records if not record.get("IsDeleted")]
    rows = [driver_result_row(record, event, teams) for record in active]
    if not rows:
        return SessionResults(columns=result_columns())
    frame = SessionResults(rows)
    return frame.sort_values("Position", na_position="last").reset_index(drop=True)


class SessionResults(pd.DataFrame):
    @property
    def _constructor(self):
        return SessionResults


def team_by_car(laps):
    if laps is None or laps.empty or "Team" not in laps.columns:
        return {}
    unique = laps.drop_duplicates("DriverNumber")
    return dict(zip(unique["DriverNumber"].astype(str), unique["Team"]))


def driver_result_row(record, event, teams):
    number = str(record.get("CarNumber", "")).strip()
    if number.isdigit():
        number = str(int(number))
    first = record.get("FirstName", "")
    last = record.get("LastName", "")
    row = {
        "DriverId": record.get("DriversID", ""),
        "FirstName": first,
        "LastName": last,
        "FullName": record.get("DriverName") or f"{first} {last}".strip(),
        "Abbreviation": abbreviation_for(last),
        "DriverNumber": number,
        "Team": record.get("TeamName") or teams.get(number, ""),
        "GridPosition": to_number(record.get("PositionStart")),
        "Position": to_number(record.get("PositionFinish")),
        "Status": record.get("Status", ""),
        "Points": to_number(record.get("PointsEarned")),
        "Laps": to_number(record.get("LapsComplete")),
        "LapsLed": to_number(record.get("LapsLed")),
        "TimesLed": to_number(record.get("TimesLed")),
        "PitStops": to_number(record.get("PitStops")),
        "FastestLapSpeed": to_float(record.get("BestSpeed")),
        "AvgLapSpeed": to_float(record.get("SpeedAvg")),
    }
    row.update(copy_race_fields(event))
    return row


def abbreviation_for(last_name):
    return str(last_name or "")[:ABBREV_LEN].upper()


def to_number(value):
    if value is None or value == "":
        return pd.NA
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return pd.NA


def to_float(value):
    if value is None or value == "":
        return pd.NA
    try:
        return float(value)
    except (TypeError, ValueError):
        return pd.NA


def copy_race_fields(event):
    return {dest: getattr(event, source, "") for source, dest in RACE_COLUMNS.items()}


def result_columns():
    return [
        "DriverId", "FirstName", "LastName", "FullName", "Abbreviation",
        "DriverNumber", "Team", "GridPosition", "Position", "Status", "Points",
        "Laps", "LapsLed", "TimesLed", "PitStops", "FastestLapSpeed",
        "AvgLapSpeed",
        *RACE_COLUMNS.values(),
    ]
