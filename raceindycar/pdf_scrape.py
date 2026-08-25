import re

import pdfplumber

from raceindycar.pdf_table import (
    clean_cell,
    clean_time,
    column_roles,
    label_columns,
    largest_data_table,
)

CAR_RE = re.compile(r"Section Data for Car (\d+)\s*-\s*(.+)")
MIN_DATA_COLS = 3
SECTION_SUM_TOLERANCE = 0.2


def parse_car_header(page):
    match = CAR_RE.search(page.extract_text() or "")
    if not match:
        return None, None
    return match.group(1), match.group(2).strip()


def metric_type(row):
    if len(row) < MIN_DATA_COLS:
        return ""
    text = clean_cell(row[1])
    return text if text in {"T", "S"} else ""


def blank_record(car_number, driver, lap):
    return {
        "car_number": car_number,
        "driver": driver,
        "lap": lap,
        "lap_time": "",
        "lap_speed": "",
        "on_pit_road": "0",
        "sections": {},
        "pits": {},
    }


def fill_sections_and_pits(record, row, roles):
    for index, label in zip(roles["section_idxs"], roles["section_labels"]):
        if label and index < len(row):
            value = clean_time(row[index])
            if value:
                record["sections"][label] = value
    for index, label in zip(roles["pit_idxs"], roles["pit_labels"]):
        if label and index < len(row):
            value = clean_time(row[index])
            if value:
                record["pits"][label] = value


def lap_column_value(row, roles):
    index = roles["lap_time_idx"]
    if index is None or index >= len(row):
        return ""
    return clean_time(row[index])


def row_to_partial(row, car_number, driver, roles, current_lap):
    metric = metric_type(row)
    lap = clean_cell(row[0]) or current_lap
    if not lap or not metric:
        return None, current_lap
    record = blank_record(car_number, driver, lap)
    if metric == "T":
        fill_sections_and_pits(record, row, roles)
        record["lap_time"] = lap_column_value(row, roles)
    else:
        record["lap_speed"] = lap_column_value(row, roles)
    return record, lap


def merge_records(base, incoming):
    if not base["lap_time"] and incoming["lap_time"]:
        base["lap_time"] = incoming["lap_time"]
    if not base["lap_speed"] and incoming["lap_speed"]:
        base["lap_speed"] = incoming["lap_speed"]
    base["sections"].update(incoming["sections"])
    base["pits"].update(incoming["pits"])
    return base


def section_sum(record):
    values = record["sections"].values()
    if not values:
        return None
    try:
        return sum(float(v) for v in values)
    except ValueError:
        return None


def resolve_lap_time(record):
    # Laps with recorded pit segments (in/out of pit road) legitimately run
    # longer than their on-track section splits sum to, so only laps with no
    # pit activity are eligible for the section-sum sanity check below.
    if record["pits"]:
        return record["lap_time"]
    total = section_sum(record)
    if total is None:
        return record["lap_time"]
    try:
        reported = float(record["lap_time"])
    except (TypeError, ValueError):
        return record["lap_time"]
    if reported and abs(reported - total) / total > SECTION_SUM_TOLERANCE:
        return f"{total:.4f}"
    return record["lap_time"]


def finalize_record(record):
    record["lap_time"] = resolve_lap_time(record)
    record["on_pit_road"] = "1" if "PI to PO" in record["pits"] else "0"
    return record


def scrape_page(page, car_number, driver):
    selected = largest_data_table(page)
    if not selected:
        return []
    table, rows = selected
    labels = label_columns(page, table)
    if not labels or len(labels) != len(rows[0]):
        return []
    roles = column_roles(labels)
    partials = []
    current_lap = ""
    for row in rows:
        partial, current_lap = row_to_partial(
            row, car_number, driver, roles, current_lap,
        )
        if partial:
            partials.append(partial)
    return partials


def scrape_pdf(pdf_path):
    merged = {}
    car_number = None
    driver = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            parsed_car, parsed_driver = parse_car_header(page)
            if parsed_car:
                car_number, driver = parsed_car, parsed_driver
            if not car_number:
                continue
            for partial in scrape_page(page, car_number, driver):
                key = (partial["car_number"], partial["lap"])
                if key in merged:
                    merge_records(merged[key], partial)
                else:
                    merged[key] = partial
    return [finalize_record(row) for row in merged.values()]


def enrichment_map(pdf_path):
    return {
        (row["car_number"], row["lap"]): {
            "lap_time": row["lap_time"],
            "lap_speed": row["lap_speed"],
            "on_pit_road": row["on_pit_road"],
        }
        for row in scrape_pdf(pdf_path)
    }
