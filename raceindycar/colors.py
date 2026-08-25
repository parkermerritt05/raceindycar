INDY_BLUE = "#0cc0df"

TEAM_COLORS = {
    "team penske": "#FFD100",
    "chip ganassi racing": "#ED1C24",
    "ganassi": "#ED1C24",
    "arrow mclaren": "#FF8000",
    "mclaren": "#FF8000",
    "andretti global": "#00A651",
    "andretti autosport": "#00A651",
    "andretti": "#00A651",
    "meyer shank racing": "#E4007C",
    "meyer shank": "#E4007C",
    "rahal letterman lanigan": "#002D62",
    "rahal": "#002D62",
    "a.j. foyt racing": "#C8102E",
    "aj foyt racing": "#C8102E",
    "foyt": "#C8102E",
    "dale coyne racing": "#00AEEF",
    "coyne": "#00AEEF",
    "prema racing": "#E10600",
    "prema": "#E10600",
    "ed carpenter racing": "#FF6600",
    "juncos hollinger": "#0057B8",
    "juncos": "#0057B8",
    "dreyer & reinbold": "#6B2D8B",
    "dreyer and reinbold": "#6B2D8B",
    "hmd motorsports": "#1B4F72",
    "abel motorsports": "#2E8B57",
}
LINESTYLES = ("-", "--", ":", "-.")
MARKERS = ("o", "s", "^", "D")


def match_team_color(name):
    needle = str(name or "").strip().casefold()
    if not needle:
        return None
    if needle in TEAM_COLORS:
        return TEAM_COLORS[needle]
    for key, color in TEAM_COLORS.items():
        if key in needle or needle in key:
            return color
    return None


def get_team_color(identifier, session=None):
    mapped = match_team_color(identifier)
    if mapped:
        return mapped
    if session is None or session.results is None:
        return INDY_BLUE
    return team_color_from_results(identifier, session)


def team_color_from_results(identifier, session):
    teams = session.results["Team"].astype(str)
    needle = str(identifier).casefold()
    hits = session.results[teams.str.casefold() == needle]
    if hits.empty:
        hits = session.results[teams.str.casefold().str.contains(needle, regex=False)]
    if hits.empty:
        return INDY_BLUE
    return match_team_color(hits.iloc[0].get("Team", "")) or INDY_BLUE


def get_driver_color(identifier, session):
    driver = session.get_driver(identifier)
    return match_team_color(driver.get("Team", "")) or INDY_BLUE


def teammate_index(driver, session):
    team = driver.get("Team", "")
    mates = session.results[session.results["Team"] == team]
    numbers = list(mates["DriverNumber"].astype(str))
    number = str(driver.get("DriverNumber", ""))
    if number in numbers:
        return numbers.index(number)
    return 0


def get_driver_style(identifier, session):
    driver = session.get_driver(identifier)
    index = teammate_index(driver, session)
    return {
        "color": get_driver_color(identifier, session),
        "linestyle": LINESTYLES[index % len(LINESTYLES)],
        "marker": MARKERS[index % len(MARKERS)],
    }
