from pathlib import Path

from raceindycar.pdf_scrape import enrichment_map, finalize_record

EXAMPLE_PRACTICE_PDF = Path(__file__).resolve().parent / "example_practice_results.pdf"
EXAMPLE_RACE_PDF = Path(__file__).resolve().parent / "example_race.pdf"


def blank_record(**overrides):
    record = {
        "car_number": "12", "driver": "Power, Will", "lap": "1",
        "lap_time": "", "lap_speed": "", "on_pit_road": "0", "caution": "0",
        "sections": {}, "pits": {},
    }
    record.update(overrides)
    return record


def test_finalize_record_flags_pit_road_only_for_pi_to_po():
    # A qualifying out-lap legitimately carries a "PO to SF" segment even
    # though the lap itself is a full-speed flying lap - it must not be
    # treated as a pit-affected lap.
    out_lap = blank_record(lap_time="38.4405", pits={"PO to SF": "47.0779"})
    assert finalize_record(out_lap)["on_pit_road"] == "0"

    real_pit_lap = blank_record(lap_time="65.1234", pits={"PI to PO": "12.5"})
    assert finalize_record(real_pit_lap)["on_pit_road"] == "1"


def test_finalize_record_corrects_lap_time_from_section_sum_when_way_off():
    # Reproduces the real Firestone Fast 6 report bug: the PDF's own "Lap"
    # total for the final timed lap is garbage (308.0633s), but the lap's
    # own section splits sum to the true value (38.4913s, confirmed against
    # the official qualifying results).
    record = blank_record(
        lap="4",
        lap_time="308.0633",
        sections={
            "Stretch Front 5": "2.8378", "Turn 1 Entry": "1.9217",
            "Turn 1 Exit": "2.8883", "Turn 2 Entry": "2.9364",
            "Turn 2 ExitBack": "1.9366", "ExitBack Stretch 1": "2.4222",
            "Back Stretch 2": "2.3914", "Back Stretch 3": "2.3740",
            "Back Stretch 4": "2.3577", "Turn 3 Entry": "1.9058",
            "Turn 3 Exit": "2.8977", "Turn 4 Entry": "2.9148",
            "Turn 4 Exit": "1.9657", "Stretch Front 1": "1.4292",
            "Stretch Front 2": "1.4179", "Stretch Front 3": "1.9566",
            "Stretch Front 4": "1.9375",
        },
    )
    assert finalize_record(record)["lap_time"] == "38.4913"


def test_finalize_record_keeps_lap_time_when_pit_segments_present():
    # A genuinely pit-affected lap legitimately runs longer than its
    # on-track section splits sum to - must not be "corrected" down.
    record = blank_record(
        lap_time="65.0000",
        sections={"Turn 1": "2.0", "Turn 2": "2.0"},
        pits={"PI to PO": "40.0"},
    )
    assert finalize_record(record)["lap_time"] == "65.0000"


def test_finalize_record_keeps_lap_time_when_within_tolerance():
    record = blank_record(
        lap_time="38.50", sections={"Turn 1": "19.0", "Turn 2": "19.4"},
    )
    assert finalize_record(record)["lap_time"] == "38.50"


def test_enrichment_map_parses_practice_section_results_pdf():
    records = enrichment_map(EXAMPLE_PRACTICE_PDF)
    assert len(records) > 0

    (car, lap), values = next(iter(records.items()))
    assert car.isdigit()
    assert lap.isdigit()
    assert set(values) == {"lap_time", "lap_speed", "on_pit_road", "caution"}

    car_2_laps = {lap: values for (c, lap), values in records.items() if c == "2"}
    assert car_2_laps["1"]["lap_time"] == "845.0893"
    assert car_2_laps["1"]["lap_speed"] == "9.619"


def test_enrichment_map_flags_caution_laps_from_yellow_section_pdf():
    # tests/example_race.pdf's first car: a caution flies partway through
    # lap 1 (its Back Stretch/Turn 3/Turn 4/Front cells are shaded yellow,
    # confirmed against the rendered page), stays yellow through lap 9
    # (also shaded partway, confirmed by the much slower pace-lap speeds),
    # then it's back to green at lap 10.
    records = enrichment_map(EXAMPLE_RACE_PDF)
    car_laps = {lap: values for (c, lap), values in records.items() if c == "2"}
    for lap in map(str, range(1, 10)):
        assert car_laps[lap]["caution"] == "1"
    assert car_laps["10"]["caution"] == "0"
