import re

HEADER_BLEED_RE = re.compile(r"^(?:Entry|Exit)\s*", re.IGNORECASE)
TIME_RE = re.compile(r"^\d+\.\d+$")
TIME_TOKEN_RE = re.compile(r"\d+\.\d+")
LAP_LABEL_RE = re.compile(r"^L\s*ap$", re.IGNORECASE)
PIT_LABEL_RE = re.compile(
    r"^(PI to PO|PO to SF|SF to PI|PO to Alt|PO S/F to Alt|Alt S/F to PI)",
    re.IGNORECASE,
)

TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
}
MIN_DATA_COLS = 3
FLAG_COLUMN_INDEX = 2
GREEN_FILL = (0.565, 0.933, 0.565)
YELLOW_FILL = (1.0, 1.0, 0.0)
FILL_TOLERANCE = 0.05


def largest_data_table(page):
    found = page.find_tables(table_settings=TABLE_SETTINGS)
    candidates = []
    for table in found:
        rows = table.extract() or []
        if rows and len(rows[0]) >= MIN_DATA_COLS:
            candidates.append((table, rows))
    if not candidates:
        return None
    return max(candidates, key=lambda item: len(item[1]) * len(item[1][0]))


def row_fill_flags(page, table):
    """Classify each row of `table` as 'yellow' (caution), 'green', or ''.

    IndyCar's Section Data report shades each timing-loop cell in a lap row
    to show whether that loop was crossed under caution (yellow) or
    green-flag racing (green) - a caution can fly mid-lap, so different
    cells in the same row can disagree; any yellow cell makes the row
    'yellow'. That shading is a filled rectangle on the page, not exposed by
    `table.extract()`'s text, so it has to be read from `page.rects`.
    """
    bounds = row_bounds(table)
    mid_xs = column_mid_xs(table)
    if not bounds or not mid_xs:
        return ["" for _ in bounds]
    fills = [
        (rect["top"], rect["bottom"], rect["x0"], rect["x1"], rect.get("non_stroking_color"))
        for rect in page.rects
        if rect.get("fill")
    ]
    flags = []
    for top, bottom in bounds:
        colors = {classify_fill(fill_color_at(fills, mid_x, top, bottom)) for mid_x in mid_xs}
        if "yellow" in colors:
            flags.append("yellow")
        elif "green" in colors:
            flags.append("green")
        else:
            flags.append("")
    return flags


def row_bounds(table):
    tops = sorted({round(top, 1) for _x0, top, _x1, _bottom in table.cells})
    if not tops:
        return []
    row_height = tops[1] - tops[0] if len(tops) > 1 else 0
    return [
        (top, tops[i + 1] if i + 1 < len(tops) else top + row_height)
        for i, top in enumerate(tops)
    ]


def column_mid_xs(table):
    cells = first_row_cells(table)[FLAG_COLUMN_INDEX:]
    return [(x0 + x1) / 2 for x0, _top, x1, _bottom in cells]


def fill_color_at(fills, mid_x, top, bottom):
    mid_y = (top + bottom) / 2
    for rtop, rbottom, rx0, rx1, color in fills:
        if rtop - 0.5 <= mid_y <= rbottom + 0.5 and rx0 - 0.5 <= mid_x <= rx1 + 0.5:
            return color
    return None


def classify_fill(color):
    if not color or len(color) != 3:
        return ""
    if colors_close(color, YELLOW_FILL):
        return "yellow"
    if colors_close(color, GREEN_FILL):
        return "green"
    return ""


def colors_close(color, target):
    return all(abs(c - t) <= FILL_TOLERANCE for c, t in zip(color, target))


def label_columns(page, table):
    row_cells = first_row_cells(table)
    if not row_cells:
        return []
    first_top = row_cells[0][1]
    words = page.extract_words()
    labels = []
    for x0, _top, x1, _bottom in row_cells:
        parts = []
        for word in words:
            mid = (word["x0"] + word["x1"]) / 2
            if mid < x0 - 1 or mid > x1 + 1:
                continue
            if word["top"] < first_top - 20 or word["top"] >= first_top - 0.5:
                continue
            if TIME_RE.fullmatch(word["text"]):
                continue
            parts.append((word["x0"], word["text"]))
        labels.append(" ".join(text for _, text in sorted(parts)))
    return repair_labels(labels)


def first_row_cells(table):
    if not table or not table.cells:
        return []
    tops = sorted({round(cell[1], 1) for cell in table.cells})
    first_top = tops[0]
    return sorted(
        [cell for cell in table.cells if abs(cell[1] - first_top) < 1],
        key=lambda cell: cell[0],
    )


def repair_labels(labels):
    labels = [normalize_label_text(label) for label in labels]
    if len(labels) > 2 and not labels[1] and labels[2].startswith("T/S"):
        labels[1] = "T/S"
        labels[2] = labels[2][3:].strip()
    labels = repair_ts_bleed(labels)
    labels = repair_split_lap_header(labels)
    labels = repair_turn_entry_split(labels)
    return labels


def normalize_label_text(text):
    text = text.replace("T/STurn", "T/S Turn")
    text = text.replace("EntryBackStretch", "Entry BackStretch")
    text = re.sub(r"\bS F\b", "SF", text)
    return re.sub(r"\s+", " ", text).strip()


def repair_ts_bleed(labels):
    if len(labels) <= 2:
        return labels
    if labels[1].startswith("T/S") and labels[1] != "T/S":
        rest = labels[1][3:].strip()
        labels[1] = "T/S"
        if rest:
            labels[2] = f"{rest} {labels[2]}".strip()
    if labels[2].startswith("to ") and not labels[2].upper().startswith("TO I"):
        labels[2] = f"SF {labels[2]}".strip()
    return labels


def repair_split_lap_header(labels):
    for index in range(len(labels) - 1):
        left = labels[index]
        right = labels[index + 1]
        if left.endswith(" L") and LAP_LABEL_RE.fullmatch(right):
            labels[index] = left[:-2].rstrip()
            labels[index + 1] = "Lap"
    for index, label in enumerate(labels):
        if LAP_LABEL_RE.fullmatch(label):
            labels[index] = "Lap"
    return labels


def repair_turn_entry_split(labels):
    for index in range(len(labels) - 1):
        if not re.fullmatch(r"Turn \d+", labels[index]):
            continue
        if not labels[index + 1].startswith("Entry"):
            continue
        labels[index] = f"{labels[index]} Entry"
        labels[index + 1] = re.sub(r"^Entry\s*", "", labels[index + 1]).strip()
    return labels


def column_roles(labels):
    lap_time_idx = find_lap_time_index(labels)
    if lap_time_idx is None:
        return {
            "section_labels": labels[2:],
            "section_idxs": list(range(2, len(labels))),
            "lap_time_idx": None,
            "pit_labels": [],
            "pit_idxs": [],
        }
    return {
        "section_labels": labels[2:lap_time_idx],
        "section_idxs": list(range(2, lap_time_idx)),
        "lap_time_idx": lap_time_idx,
        "pit_labels": labels[lap_time_idx + 1 :],
        "pit_idxs": list(range(lap_time_idx + 1, len(labels))),
    }


def find_lap_time_index(labels):
    for index, label in enumerate(labels[2:], start=2):
        if is_lap_label(label):
            return index
    for index, label in enumerate(labels[2:], start=2):
        if is_pit_label(label):
            return index - 1 if index > 2 else None
    return None


def is_lap_label(label):
    text = label or ""
    if text == "Lap" or bool(LAP_LABEL_RE.fullmatch(text)):
        return True
    return text.startswith("Lap ")


def is_pit_label(label):
    return bool(PIT_LABEL_RE.match(label or ""))


def clean_cell(value):
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    return HEADER_BLEED_RE.sub("", text).strip()


def clean_time(value):
    text = clean_cell(value)
    if TIME_RE.fullmatch(text):
        return text
    # Column-header text sometimes bleeds into a data cell (e.g. "Stretch
    # 5\n2.8407"); the real value is always the trailing decimal token.
    matches = TIME_TOKEN_RE.findall(text)
    return matches[-1] if matches else ""
