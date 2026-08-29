"""Manual smoke test for every symbol exported from raceindycar/__init__.py.

Not a pytest suite - hits the real IndyCar site/PDF reports. Run directly
and read the printed output:

    python manual.py
"""

print("importing time")
from time import perf_counter
run_start = perf_counter()
print("importing pandas")
start = perf_counter()

print("importing raceindycar")
import raceindycar
print(f"Improted in {perf_counter() - start} seconds")
print("Init globals")

CACHE_DIR = ".cache/fastindycar"
YEAR = 2024
RACE_NAME = "Indianapolis 500"

print("setting log level")
# --- set_log_level ---
raceindycar.set_log_level("INFO")

# --- enable_cache / Cache ---
print("enabling cahce")
start = perf_counter()
raceindycar.enable_cache(CACHE_DIR, cache_format="csv")
print(f"cache info in {perf_counter() - start}:", raceindycar.Cache.get_cache_info())

# --- get_event_schedule / EventSchedule ---
start = perf_counter()
schedule = raceindycar.get_event_schedule(YEAR)
print(f"\n{YEAR} schedule ({len(schedule)} races) loaded in {perf_counter() - start:.3f}s:")
print(schedule)

event_by_name = schedule.get_event_by_name(RACE_NAME)
print("\nEventSchedule.get_event_by_name:", event_by_name)

# --- get_event / Event ---
start = perf_counter()
event_by_round = raceindycar.get_event(YEAR, 1)
print(f"\nby round number ({perf_counter() - start:.3f}s):", event_by_round)

start = perf_counter()
event_by_id = raceindycar.get_event(YEAR, event_by_round.race_id)
print(f"by race_id ({perf_counter() - start:.3f}s):", event_by_id)

start = perf_counter()
event_by_fuzzy_name = raceindycar.get_event(YEAR, "Indianapoli 500")
print(f"by fuzzy name ({perf_counter() - start:.3f}s):", event_by_fuzzy_name)

print("Event.sessions:", event_by_fuzzy_name.sessions)

try:
    raceindycar.get_event(YEAR, 999)
except ValueError as exc:
    print(f"expected error (bad round): {exc}")

try:
    raceindycar.get_event(YEAR, "Not A Real Race")
except ValueError as exc:
    print(f"expected error (bad name): {exc}")

# --- Event.get_session / get_session / Session ---
start = perf_counter()
session_via_event = event_by_fuzzy_name.get_session("R")
print(f"\nSession (via Event.get_session, {perf_counter() - start:.3f}s):", session_via_event)

start = perf_counter()
session = raceindycar.get_session(YEAR, RACE_NAME, "R")
print(f"Session (via top-level get_session, {perf_counter() - start:.3f}s):", session)

start = perf_counter()
session.load()
print(f"session.load() took {perf_counter() - start:.3f}s")

# --- SessionResults ---
print("\nsession.results.head():")
print(session.results.head())

# --- Session.get_driver ---
driver_by_name = session.get_driver("Josef Newgarden")
print("\nget_driver by name:", driver_by_name["FullName"])
driver_by_number = session.get_driver(driver_by_name["DriverNumber"])
driver_by_abbr = session.get_driver(driver_by_name["Abbreviation"])
assert (
    driver_by_name["DriverId"] == driver_by_number["DriverId"] == driver_by_abbr["DriverId"]
)
print("lookup by number/abbreviation agree with lookup by name")

try:
    session.get_driver("Not A Real Driver")
except KeyError as exc:
    print(f"expected error (unknown driver): {exc}")

# --- Laps ---
laps = session.laps
print(f"\nsession.laps: {len(laps)} rows")
print(laps.head())

print("\npick_drivers:")
print(laps.pick_drivers([driver_by_name["DriverNumber"], "2"]).head())

print("\npick_teams:")
print(laps.pick_teams(driver_by_name["Team"]).head())

print("\npick_wo_pit:")
print(laps.pick_wo_pit().head())

print("\npick_quicklaps:")
print(laps.pick_quicklaps().head())

print("\npick_fastest:")
print(laps.pick_fastest())

print("\npick_laps(range(1, 6)):")
print(laps.pick_laps(range(1, 6)).head())

# --- Cache: offline / disabled / ci / enable-disable / delete_response ---
raceindycar.Cache.offline_mode(True)
start = perf_counter()
session.load()
print(f"\noffline reload took {perf_counter() - start:.3f}s (cache only, no network)")
raceindycar.Cache.offline_mode(False)

with raceindycar.Cache.disabled():
    start = perf_counter()
    session.load()
    print(f"Cache.disabled() load took {perf_counter() - start:.3f}s (fresh network fetch)")

raceindycar.Cache.ci_mode(True)
print("Cache.ci after ci_mode(True):", raceindycar.Cache.ci)
raceindycar.Cache.ci_mode(False)
print("Cache.ci after ci_mode(False):", raceindycar.Cache.ci)

raceindycar.Cache.set_disabled()
print("Cache.enabled after set_disabled():", raceindycar.Cache.enabled)
raceindycar.Cache.set_enabled()
print("Cache.enabled after set_enabled():", raceindycar.Cache.enabled)

raceindycar.Cache.delete_response("https://www.indycar.com/does-not-matter")
print("delete_response() ran without error")

print("\ncache info before clear:", raceindycar.Cache.get_cache_info())
# Uncomment to actually wipe the on-disk cache built up by this run:
# raceindycar.Cache.clear_cache()
# print("cache info after clear:", raceindycar.Cache.get_cache_info())

print(f"\ntotal runtime: {perf_counter() - run_start:.3f}s")
