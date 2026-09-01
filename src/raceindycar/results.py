import pandas as pd

from raceindycar.frames import drop_empty_columns

ABBREV_LEN = 3
RACE_COLUMNS = {
    "race_id": "RaceId",
    "EventName": "RaceName",
    "date": "Date",
    "track_type": "TrackType",
    "actual_laps": "ActualLaps",
}
REQUIRED_RESULT_FIELDS = {
    "DriversID", "FirstName", "LastName", "FullName", "Abbreviation",
    "CarNumber", "Team", "PositionFinish", *RACE_COLUMNS.values(),
}
NUMBER_COERCED_FIELDS = {
    "PositionStart", "PositionFinish", "PointsEarned",
    "LapsComplete", "LapsLed", "TimesLed", "PitStops",
}
FLOAT_COERCED_FIELDS = {"BestSpeed", "SpeedAvg"}


def build_results(records, event, laps=None):
    teams = team_by_car(laps)
    active = [record for record in records if not record.get("IsDeleted")]
    rows = [driver_result_row(record, event, teams) for record in active]
    if not rows:
        return SessionResults(columns=result_columns())
    frame = SessionResults(rows)
    frame = frame.sort_values("PositionFinish", na_position="last").reset_index(drop=True)
    return drop_empty_columns(frame, REQUIRED_RESULT_FIELDS)


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

    row = dict(record)
    for field in NUMBER_COERCED_FIELDS:
        if field in row:
            row[field] = to_number(row[field])
    for field in FLOAT_COERCED_FIELDS:
        if field in row:
            row[field] = to_float(row[field])
    row["FullName"] = record.get("DriverName") or f"{first} {last}".strip()
    row["Abbreviation"] = abbreviation_for(last)
    row["Team"] = record.get("TeamName") or teams.get(number, "")
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
    return {dest: str(getattr(event, source, "")) for source, dest in RACE_COLUMNS.items()}


def result_columns():
    return sorted(REQUIRED_RESULT_FIELDS)
