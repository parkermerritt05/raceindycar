from raceindycar.pdf_lapchart import parse_page, scrape_pdf

PAGE_1 = "\n".join([
    "Event: Test GP",
    "Track: Test Track",
    "Report: Race Lap Chart NTT INDYCAR SERIES",
    "Session: Race 1 January 1, 2024",
    "1 1 1",
    "Drivers in Race: Lap-> 1 2 3",
    "3 - McLaughlin, Scott (1) 1 3 5 5",
    "5 - O'Ward, Pato (2) 2 5 3 3",
    "7 - Rossi, Alexander (5) 3 66",
    "Pit Stop Fastest Lap Lapped Car",
    "Page 1 of 1 Information provided by Indy Racing Information System",
])


def test_parse_page_inverts_rank_rows_into_car_positions():
    positions, next_offset = parse_page(PAGE_1, lap_offset=0)
    assert next_offset == 3
    assert positions[("3", "1")] == 1
    assert positions[("5", "1")] == 2
    assert positions[("3", "2")] == 2
    assert positions[("5", "2")] == 1
    assert positions[("3", "3")] == 2
    assert positions[("5", "3")] == 1


def test_parse_page_handles_retired_driver_short_row():
    positions, _ = parse_page(PAGE_1, lap_offset=0)
    assert positions[("66", "1")] == 3
    assert ("66", "2") not in positions
    assert ("66", "3") not in positions


def test_parse_page_ignores_footer_lines():
    positions, _ = parse_page(PAGE_1, lap_offset=0)
    # 3 laps for car 3, 3 for car 5, 1 for retired car 66 - footer lines
    # ("Pit Stop Fastest Lap...", "Page 1 of 1...") contribute nothing.
    assert len(positions) == 7


def test_parse_page_continues_lap_offset_across_pages():
    _, offset_after_page1 = parse_page(PAGE_1, lap_offset=0)
    page_2 = PAGE_1.replace(
        "Drivers in Race: Lap-> 1 2 3", "Drivers in Race: Lap-> 4 5 6",
    )
    positions, next_offset = parse_page(page_2, lap_offset=offset_after_page1)
    assert next_offset == 6
    assert positions[("3", "4")] == 1
    assert positions[("5", "6")] == 1


def test_parse_page_missing_header_returns_empty():
    positions, next_offset = parse_page("no header here", lap_offset=5)
    assert positions == {}
    assert next_offset == 5


def test_scrape_pdf_matches_known_real_race_positions(monkeypatch):
    class FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class FakePdf:
        def __init__(self, pages):
            self.pages = pages

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    import raceindycar.pdf_lapchart as module

    monkeypatch.setattr(
        module.pdfplumber, "open", lambda path: FakePdf([FakePage(PAGE_1)]),
    )
    positions = scrape_pdf("ignored.pdf")
    assert positions[("3", "1")] == 1
    assert positions[("5", "3")] == 1
