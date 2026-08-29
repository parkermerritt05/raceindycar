# fastindycar

A [FastF1](https://github.com/theOehrly/Fast-F1)-style Python interface for
IndyCar data: event schedules, session results, lap-by-lap timing, and
quick plotting helpers, built on top of publicly available IndyCar timing
and scoring data.

## Installation

```bash
pip install -e .
```

Requires Python 3.10+. Dependencies (`pandas`, `requests`, `requests-cache`,
`pdfplumber`, `matplotlib`) are installed automatically.

## Quick start

```python
import raceindycar

# Optional: cache scraped/parsed data to disk between runs
raceindycar.enable_cache(cache_dir=".cache/fastindycar")

# Look up the schedule for a season
schedule = raceindycar.get_event_schedule(2024)

# Get a specific event (by race id or fuzzy name match)
event = raceindycar.get_event(2024, "Indianapolis 500")

# Load a session's results and lap data
session = raceindycar.get_session(2024, "Indianapolis 500")
session.load()

session.results     # SessionResults: a pandas DataFrame of finishing order
session.laps        # Laps: a pandas DataFrame of lap-by-lap timing

# Look up a single driver from the loaded results
driver = session.get_driver("Josef Newgarden")  # or car number / abbreviation
```

## Working with laps and results

`Laps` and `SessionResults` are pandas `DataFrame` subclasses, so all normal
pandas operations work. `Laps` adds a few convenience filters:

```python
session.laps.pick_drivers(["12", "2"])   # by car number or driver name
session.laps.pick_teams("Team Penske")
session.laps.pick_wo_pit()               # exclude pit-road laps
session.laps.pick_quicklaps()            # laps within threshold of fastest
session.laps.pick_fastest()
session.laps.pick_laps(range(1, 21))
```

## Plotting

```python
from raceindycar import plotting

plotting.setup_mpl()
fig, ax = plotting.plot_position(session, drivers=["12", "2"])
fig, ax = plotting.plot_lap_times(session, drivers=["12", "2"])
fig, ax = plotting.plot_bar(session, metric="Position")
```

## Historical data

`raceindycar.history` builds a season-by-season results table by scraping
IndyCar's historical race archive:

```python
from raceindycar.history import historical_rows

rows, failed = historical_rows(min_year=1996)
```

## Caching

This mirrors [FastF1's `Cache`](https://docs.fastf1.dev/api_reference/cache_and_rate_limits.html)
API. Caching happens in two stages: raw HTTP responses are cached in a local
sqlite database (via `requests-cache`), and fully-parsed session payloads are
cached as pickle files by default, or as a directory of CSV files if you pass
`cache_format="csv"`. Both are stored under the `cache_dir` you provide - there
is no default location, so `cache_dir` is required:

```python
raceindycar.enable_cache(cache_dir=".cache/fastindycar", force_renew=False)
# raceindycar.enable_cache(cache_dir=".cache/fastindycar", cache_format="csv")

from raceindycar.cache import Cache
Cache.clear_cache()          # wipe Stage 2 (parsed/pickle) data, keep the HTTP cache
Cache.clear_cache(deep=True) # also wipe the Stage 1 HTTP cache
Cache.offline_mode(True)     # never hit the network; raise if nothing is cached
Cache.ci_mode(True)          # reuse expired HTTP cache entries; skip Stage 2 caching
Cache.delete_response(url)   # drop a single cached HTTP response
with Cache.disabled():
    ...                      # temporarily bypass the cache

# Requests are also rate-limited (soft throttling, then a hard
# raceindycar.exceptions.RateLimitExceededError); cache hits don't count.
```

## Development

```bash
pip install -e . pytest
pytest
```

## License

MIT — see [LICENSE](LICENSE).
