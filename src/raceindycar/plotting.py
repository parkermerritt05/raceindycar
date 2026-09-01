import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from raceindycar.colors import get_driver_color, get_driver_style, get_team_color
from raceindycar.laps import as_list

GRID_ALPHA = 0.08
SPINE_COLOR = "#bbbbbb"
LABEL_COLOR = "#333333"
TICK_COLOR = "#444444"
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


def plot_position(session, drivers=None, id_col=None, ax=None):
    fig, ax = ensure_axes(ax)
    laps = session.laps if drivers is None else session.laps.pick_drivers(drivers, column=id_col)
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


def driver_label(laps):
    if laps.empty:
        return ""
    return laps["Driver"].iloc[0]


def plot_lap_times(session, drivers, id_col=None, ax=None):
    fig, ax = ensure_axes(ax)
    for driver in as_list(drivers):
        laps = session.laps.pick_drivers(driver, column=id_col).pick_wo_pit()
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


def plot_qualifying_vs_finish(df, qualifying_col="PositionStart", finish_col="PositionFinish", ax=None):
    fig, ax = ensure_axes(ax)
    x = df[qualifying_col]
    y = df[finish_col]
    ax.scatter(x, y, alpha=0.5, s=25)
    _plot_trend_line(ax, x, y)
    ax.set_xlabel("Start")
    ax.set_ylabel("Finish")
    return fig, ax


def plot_position_gain(df, qualifying_col="PositionStart", finish_col="PositionFinish", gain_col=None, ax=None):
    fig, ax = ensure_axes(ax)
    gain = df[gain_col] if gain_col is not None else df[qualifying_col] - df[finish_col]
    ax.hist(gain.dropna(), bins=30)
    ax.axvline(0, linestyle="--", color="black")
    ax.set_xlabel("Positions gained (+) / lost (-)")
    ax.set_ylabel("Count")
    return fig, ax


def plot_metric_vs_qualifying(df, metric_col, qualifying_col="PositionStart", ax=None):
    fig, ax = ensure_axes(ax)
    x = df[qualifying_col]
    y = df[metric_col]
    ax.scatter(x, y, alpha=0.5, s=25)
    _plot_trend_line(ax, x, y)
    ax.set_xlabel(qualifying_col)
    ax.set_ylabel(metric_col)
    return fig, ax


def plot_driver_trajectory(
    df, id_col, id_value, order_col,
    qualifying_col="PositionStart", finish_col="PositionFinish", label_col=None, ax=None,
):
    fig, ax = ensure_axes(ax)
    hist = df[df[id_col] == id_value].sort_values(order_col)
    x = range(len(hist))
    ax.plot(x, hist[qualifying_col], marker="o", label="Start")
    ax.plot(x, hist[finish_col], marker="o", label="Finish")
    ax.invert_yaxis()
    ax.set_xticks(list(x))
    labels = hist[label_col] if label_col is not None else hist[order_col]
    ax.set_xticklabels(labels.astype(str).tolist(), rotation=45, ha="right")
    ax.set_ylabel("Position")
    ax.legend(frameon=False, fontsize=8)
    return fig, ax


def _plot_trend_line(ax, x, y):
    valid = x.notna() & y.notna()
    x, y = x[valid], y[valid]
    if len(x) < 2 or x.nunique() < 2:
        return
    coeffs = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, np.polyval(coeffs, xs), color="tab:blue")


__all__ = [
    "get_driver_color",
    "get_driver_style",
    "get_team_color",
    "plot_driver_trajectory",
    "plot_lap_times",
    "plot_metric_vs_qualifying",
    "plot_position",
    "plot_position_gain",
    "plot_qualifying_vs_finish",
    "setup_mpl",
]
