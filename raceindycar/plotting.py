import matplotlib.pyplot as plt
import pandas as pd

from raceindycar.colors import get_driver_color, get_driver_style, get_team_color
from raceindycar.laps import as_list

GRID_ALPHA = 0.08
SPINE_COLOR = "#bbbbbb"
LABEL_COLOR = "#333333"
TICK_COLOR = "#444444"
CAUTION_ALPHA = 0.06
WHITE = "#ffffff"
FONT_FAMILY = "sans-serif"
FONT_NAME = "DejaVu Sans"


def setup_mpl():
    plt.rcParams.update({
        "figure.facecolor": WHITE,
        "axes.facecolor": WHITE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": True,
        "axes.spines.bottom": True,
        "axes.edgecolor": SPINE_COLOR,
        "axes.grid": True,
        "grid.alpha": GRID_ALPHA,
        "grid.color": "#000000",
        "grid.linewidth": 0.6,
        "font.family": FONT_FAMILY,
        "font.sans-serif": [FONT_NAME, "DejaVu Sans"],
        "text.color": LABEL_COLOR,
        "axes.labelcolor": LABEL_COLOR,
        "xtick.color": TICK_COLOR,
        "ytick.color": TICK_COLOR,
    })


def plot_position(session, drivers=None, ax=None):
    fig, ax = ensure_axes(ax)
    laps = session.laps if drivers is None else session.laps.pick_drivers(drivers)
    shade_cautions(ax, session)
    for number, group in laps.groupby("DriverNumber"):
        ordered = group.sort_values("LapNumber")
        style = get_driver_style(number, session)
        ax.plot(
            ordered["LapNumber"], ordered["Position"],
            label=driver_label(ordered), color=style["color"],
            linestyle=style["linestyle"], linewidth=1.6,
        )
    ax.invert_yaxis()
    ax.set_xlabel("Lap")
    ax.set_ylabel("Position")
    ax.legend(frameon=False, fontsize=8)
    return fig, ax


def ensure_axes(ax, figsize=(8, 5)):
    if ax is not None:
        return ax.figure, ax
    fig, ax = plt.subplots(figsize=figsize, facecolor=WHITE)
    ax.set_facecolor(WHITE)
    return fig, ax


def shade_cautions(ax, session):
    if session.cautions is None or session.cautions.empty:
        return
    for row in session.cautions.itertuples(index=False):
        ax.axvspan(row.Start, row.End, color="#000000", alpha=CAUTION_ALPHA, lw=0)


def driver_label(laps):
    if laps.empty:
        return ""
    return laps["Driver"].iloc[0]


def plot_lap_times(session, drivers, ax=None):
    fig, ax = ensure_axes(ax)
    for driver in as_list(drivers):
        laps = session.laps.pick_drivers(driver).pick_wo_pit()
        ordered = laps.sort_values("LapNumber")
        style = get_driver_style(driver, session)
        ax.plot(
            ordered["LapNumber"], ordered["LapTime"],
            label=driver_label(ordered), color=style["color"],
            linestyle=style["linestyle"], linewidth=1.6,
        )
    ax.set_xlabel("Lap")
    ax.set_ylabel("Lap time (s)")
    ax.legend(frameon=False, fontsize=8)
    return fig, ax


def plot_bar(session, metric="Position", ax=None):
    fig, ax = ensure_axes(ax, figsize=(8, 7))
    frame = session.results.copy()
    frame["_value"] = pd.to_numeric(frame[metric], errors="coerce")
    frame = frame.dropna(subset=["_value"])
    frame = frame.sort_values("_value", ascending=bar_sort_ascending(metric))
    labels = frame["Abbreviation"].tolist()
    values = frame["_value"].tolist()
    colors = [get_driver_color(label, session) for label in labels]
    ax.barh(labels, values, color=colors, height=0.72)
    ax.invert_yaxis()
    for index, value in enumerate(values):
        ax.text(value, index, f" {format_bar_value(value)}", va="center", fontsize=8)
    ax.set_xlabel(metric)
    return fig, ax


def bar_sort_ascending(metric):
    return metric.casefold() in {"position", "gridposition"}


def format_bar_value(value):
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


__all__ = [
    "get_driver_color",
    "get_driver_style",
    "get_team_color",
    "plot_bar",
    "plot_lap_times",
    "plot_position",
    "setup_mpl",
]
