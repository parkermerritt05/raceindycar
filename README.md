## RaceIndyCar Intro

RaceIndyCar is a Python pip-installable package to obtain and analyze IndyCar data. By scraping information from the official IndyCar.com website, we can examine all weekend events and their corresponding sessions.

The specific information we have available depends on the session and release date. For example, not all races have the same number of practice sessions. Additionally, Lap-by-lap data is only available for 2013 and beyond (with all data being from 1996-Present).

## Installation

RaceIndyCar is pip installable, or available on [PyPI](https://pypi.org/project/raceindycar)

```bash
pip install raceindycar
```

Requires Python 3.10+. Dependencies (`pandas`, `requests`, `requests-cache`, `pdfplumber`, `matplotlib`) are installed automatically.

## Data Retrieval

In an IndyCar season, there are around 17 race events that occur. Each race event typically spans a weekend, where within that event there are individual sessions (such as practices, qualifying, and the race itself). We use this idea of events and sessions in our implementation:

```python
import raceindycar

# Get all events for a given year
races = raceindycar.get_season_events(2025)

# Returns an Event with attributes for each schedule column. The second argument does a fuzzy name match to find an event, or use a round number/integer event id found in the schedule.
indy25 = raceindycar.get_event(2025, "Indianapolis 500")

# Identify all sessions (such as practices and qualifying) for the event.
session_info = indy25.sessions

# Get a specific session from an event. The session argument can either be an EventsSessionID or a SessionName string (you can find what's available using session_info)
race_session = indy25.get_session(session="R")

# Load data for that session, and optionally loads all lap-by-lap data
race_session.load()

# A Pandas Dataframe of race data, including start position, finish position, average speed, etc.
race_session.results
```

It is not required to get an event and then get a session from that event as shown above. We can go straight to a session for a weekend:
 
```Python
det25_race = raceindycar.get_session(2025, "Detroit Grand Prix", session="R")
```

From a session, we can obtain the lap-by-lap data, with information on every section of an indycar track. Lap results from a given session are scraped from pdfs that are around 500 pages long, so loading laps can take anywhere from 30-100 seconds.

```Python
race_session.load(laps=True)

# A Pandas Dataframe of each lap, including sectional and position data
laps = race_session.laps
```

Additionally, there are some convenience filters for lap data for accessibility. Note that teams names and drivers can either be a string or a list:

```Python
laps.pick_drivers(["12", "2"]) # Use car number or driver name.
laps.pick_teams("Team Penske")

laps.pick_wo_pit() # Excludes pit-road laps
laps.pick_quicklaps(threshold=1.07) # Laps within threshold of fastest.
laps.pick_fastest()
laps.pick_laps(range(1, 21))
```

## Plotting

RaceIndyCar also offers six plotting functions with preset colors for drivers and teams. The default arguments for all of these functions will work for the given IndyCar data, but can be manipulated to take in an arbitrary racing dataframe.

The first two plotting functions can be run for drivers of a specified race.

```Python
import matplotlib.pyplot as plt
from raceindycar import plotting

det25_race.load(laps=True)

drivers = ["10", "5"]

# Set up default coloring
plotting.setup_mpl()

# Position-by-lap line chart
fig, ax = plotting.plot_position(det25_race, drivers=drivers)

# Lap time line chart
fig, ax = plotting.plot_lap_times(det25_race, drivers=drivers)

plt.show()
```

Additionally, we can plot information for multiple races:

```Python
import pandas as pd

det26_race = raceindycar.get_session(2026, "Detroit Grand Prix", session="R")
det26_race.load(laps=True)

combined_results = pd.concat([
    det25_race.results.assign(Year=2025),
    det26_race.results.assign(Year=2026),
])

# Scatter of starting position vs finishing position with trend line
fig, ax = plotting.plot_qualifying_vs_finish(combined_results)

# Histogram of positions gained/lost from start to finish
fig, ax = plotting.plot_position_gain(combined_results)

# Scatter of a results metric vs qualifying position, with trend line
fig, ax = plotting.plot_metric_vs_qualifying(combined_results, metric_col="PointsEarned")

# Plots a driver's start and finish position
fig, ax = plotting.plot_driver_trajectory(
    combined_results, id_col="FullName", id_value="Alex Palou", order_col="Year",
)

plt.show()
```

## Caching

This library mirrors [FastF1's `Cache`](https://docs.fastf1.dev/api_reference/cache_and_rate_limits.html) API, and there are two stages for caching. The first stage uses an sqlite table to store HTTP requests and results for IndyCar.com. The second stage stores Pickle/CSV files that contain information from loading a race.

Requests are rate limited to around one request per two seconds.

```Python
from raceindycar.cache import Cache

# Enable Cache with specified directory. Use either "pickle" or "csv" format.
raceindycar.enable_cache(cache_dir=".cache/raceindycar", cache_format="pickle")

# Wipe Stage 2 (parsed/pickle) data, keep the HTTP cache. Optionally, wipe all Stage 1 HTTP requests with deep=True.
Cache.clear_cache(deep=False)

# Never hit the network and only uses cached data, raising an error if the data is not found locally.
Cache.offline_mode(True)

with Cache.disabled():
    ...  # temporarily bypass the cache
```

## Summary and Application

Through utilizing official IndyCar.com data, RaceIndyCar obtains session level data, even down to individual section times for every lap. We can store this information for reuse and plot key metrics.

Applying this at a weekend level, we can see how qualifying lap times associate with race lap times for individual drivers. On a multi-race level, we can start to identify patterns and trends to create actionable results, such as identifying optimal practice time, resource allocation to adjusting the car from qualifying to race day, and more.

## Development

```bash
pip install -e . pytest
pytest
```

## License

MIT — see [LICENSE](LICENSE).
