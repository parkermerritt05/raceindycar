import pandas as pd


def drop_empty_columns(frame, protect):
    if frame.empty:
        return frame
    droppable = [col for col in frame.columns if col not in protect]
    if not droppable:
        return frame
    blank = frame[droppable].replace("", pd.NA).isna().all()
    return frame.drop(columns=blank[blank].index)
