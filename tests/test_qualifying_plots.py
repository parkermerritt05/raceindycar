import matplotlib
matplotlib.use("Agg")

import pandas as pd

from raceindycar.plotting import (
    plot_driver_trajectory,
    plot_metric_vs_qualifying,
    plot_position_gain,
    plot_qualifying_vs_finish,
)


def results_frame():
    return pd.DataFrame({
        "DriversID": ["A", "B", "C", "D"],
        "PositionStart": [1, 2, 3, 4],
        "PositionFinish": [2, 1, 4, 3],
        "RaceId": ["5001", "5001", "5001", "5001"],
        "Team": ["Penske", "Ganassi", "Penske", "Ganassi"],
        "FastestLapSpeed": [220.1, 221.5, 219.8, 218.2],
    })


def other_series_frame():
    return pd.DataFrame({
        "car": ["X", "Y", "Z"],
        "start_pos": [3, 1, 2],
        "end_pos": [1, 2, 3],
        "event": ["r1", "r1", "r1"],
    })


def test_plot_qualifying_vs_finish_defaults():
    fig, ax = plot_qualifying_vs_finish(results_frame())
    assert fig is not None and ax is not None


def test_plot_qualifying_vs_finish_custom_columns():
    fig, ax = plot_qualifying_vs_finish(
        other_series_frame(), qualifying_col="start_pos", finish_col="end_pos",
    )
    assert fig is not None and ax is not None


def test_plot_position_gain_matches_hand_computed_values():
    fig, ax = plot_position_gain(results_frame())
    # GridPosition - Position = [1-2, 2-1, 3-4, 4-3] = [-1, 1, -1, 1]
    heights = [p.get_height() for p in ax.patches if p.get_height() > 0]
    assert sum(heights) == 4


def test_plot_position_gain_uses_explicit_gain_col():
    df = results_frame()
    df["PrecomputedGain"] = [10, 10, 10, 10]
    fig, ax = plot_position_gain(df, gain_col="PrecomputedGain")
    heights = [p.get_height() for p in ax.patches if p.get_height() > 0]
    assert sum(heights) == 4


def test_plot_metric_vs_qualifying_custom_metric():
    fig, ax = plot_metric_vs_qualifying(results_frame(), metric_col="FastestLapSpeed")
    assert fig is not None and ax is not None


def test_plot_metric_vs_qualifying_custom_columns():
    df = other_series_frame()
    df["speed"] = [100.0, 101.0, 99.0]
    fig, ax = plot_metric_vs_qualifying(df, metric_col="speed", qualifying_col="start_pos")
    assert fig is not None and ax is not None


def test_plot_driver_trajectory_orders_and_filters():
    df = pd.DataFrame({
        "DriversID": ["A", "A", "A", "B"],
        "RaceId": ["r3", "r1", "r2", "r1"],
        "PositionStart": [5, 1, 3, 9],
        "PositionFinish": [4, 2, 3, 9],
    })
    fig, ax = plot_driver_trajectory(df, id_col="DriversID", id_value="A", order_col="RaceId")
    lines = ax.get_lines()
    qualifying_line, finish_line = lines[0], lines[1]
    assert list(qualifying_line.get_ydata()) == [1, 3, 5]
    assert list(finish_line.get_ydata()) == [2, 3, 4]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["r1", "r2", "r3"]


def test_plot_driver_trajectory_custom_columns():
    df = pd.DataFrame({
        "car": ["X", "X", "Y"],
        "event": ["r2", "r1", "r1"],
        "start_pos": [4, 2, 9],
        "end_pos": [3, 1, 9],
    })
    fig, ax = plot_driver_trajectory(
        df, id_col="car", id_value="X", order_col="event",
        qualifying_col="start_pos", finish_col="end_pos",
    )
    lines = ax.get_lines()
    assert list(lines[0].get_ydata()) == [2, 4]
