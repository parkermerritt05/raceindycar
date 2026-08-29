import pandas as pd

QUICKLAP_THRESHOLD = 1.07
TRUTHY_FLAGS = {"1", "true", "yes"}
LAP_COLUMNS = {
    "driver_name": "Driver",
    "car_number": "DriverNumber",
    "lap_number": "LapNumber",
    "position": "Position",
    "lap_speed": "LapSpeed",
    "lap_time": "LapTime",
    "on_pit_road": "OnPitRoad",
    "team": "Team",
}
LAP_FIELDS = list(LAP_COLUMNS.values())
NUMERIC_FIELDS = ("LapNumber", "Position", "LapTime", "LapSpeed")


def build_laps(rows):
    if not rows:
        return Laps(columns=LAP_FIELDS)
    frame = pd.DataFrame(rows).rename(columns=LAP_COLUMNS)
    for field in LAP_FIELDS:
        if field not in frame.columns:
            frame[field] = ""
    frame = coerce_numeric(normalize_numbers(frame))
    return Laps(frame[LAP_FIELDS])


def normalize_numbers(frame):
    if "DriverNumber" not in frame.columns:
        return frame
    frame["DriverNumber"] = frame["DriverNumber"].map(compact_car_number)
    return frame


def compact_car_number(value):
    text = str(value).strip()
    return str(int(text)) if text.isdigit() else text


def coerce_numeric(frame):
    for field in NUMERIC_FIELDS:
        if field in frame.columns:
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
    return frame


class Laps(pd.DataFrame):
    @property
    def _constructor(self):
        return Laps

    def pick_laps(self, laps):
        wanted = {int(lap) for lap in as_list(laps)}
        numbers = pd.to_numeric(self["LapNumber"], errors="coerce")
        return self[numbers.isin(wanted)]

    def pick_teams(self, teams):
        wanted = {str(team).casefold() for team in as_list(teams)}
        names = self["Team"].astype(str).str.casefold()
        return self[names.isin(wanted)]

    def pick_wo_pit(self):
        return self[~self["OnPitRoad"].map(is_pit)]

    def pick_fastest(self):
        times = pd.to_numeric(self["LapTime"], errors="coerce")
        if times.isna().all():
            return None
        return self.loc[times.idxmin()]

    def pick_quicklaps(self, threshold=QUICKLAP_THRESHOLD):
        racing = self.pick_wo_pit()
        times = pd.to_numeric(racing["LapTime"], errors="coerce")
        fastest = times.min()
        if pd.isna(fastest):
            return self.iloc[0:0]
        return racing[times <= fastest * threshold]

    def pick_drivers(self, drivers):
        mask = False
        for driver in as_list(drivers):
            mask = mask | self._driver_mask(driver)
        return self[mask]

    def _driver_mask(self, driver):
        text = str(driver).strip()
        numbers = self["DriverNumber"].astype(str)
        if text.isdigit():
            return numbers == str(int(text))
        names = self["Driver"].astype(str).str.casefold()
        return names == text.casefold()


def as_list(value):
    if isinstance(value, (list, tuple, set, range)):
        return list(value)
    return [value]


def is_pit(value):
    return str(value).strip().casefold() in TRUTHY_FLAGS
