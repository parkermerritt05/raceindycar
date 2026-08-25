import re

import pdfplumber

DRIVERS_HEADER = "Drivers in Race:"
ROW_RE = re.compile(r"^\d+\s*-\s*.+?\(\d+\)\s*(.*)$")


def normalize_car(value):
    text = str(value or "").strip()
    return str(int(text)) if text.isdigit() else text


def page_lap_count(lines, header_idx):
    if header_idx == 0:
        return 0
    return len(lines[header_idx - 1].split())


def row_values(line):
    match = ROW_RE.match(line.strip())
    if not match:
        return None
    # Each row is one race rank (row order = rank, 1st row = P1, ...); the
    # leading token just echoes the rank number and isn't a per-lap value.
    return match.group(1).split()[1:]


def parse_page(text, lap_offset):
    lines = text.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith(DRIVERS_HEADER)), None,
    )
    if header_idx is None:
        return {}, lap_offset
    lap_count = page_lap_count(lines, header_idx)
    positions = {}
    rank = 0
    for line in lines[header_idx + 1:]:
        values = row_values(line)
        if values is None:
            continue
        rank += 1
        for index, car_token in enumerate(values):
            car = normalize_car(car_token)
            positions[(car, str(lap_offset + index + 1))] = rank
    return positions, lap_offset + lap_count


def scrape_pdf(pdf_path):
    positions = {}
    lap_offset = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_positions, lap_offset = parse_page(page.extract_text() or "", lap_offset)
            positions.update(page_positions)
    return positions


def position_map(pdf_path):
    return scrape_pdf(pdf_path)
