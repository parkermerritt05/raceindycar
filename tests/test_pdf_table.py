from raceindycar.pdf_table import (
    clean_time,
    column_roles,
    find_lap_time_index,
    repair_split_lap_header,
    repair_turn_entry_split,
    repair_ts_bleed,
)


def test_repair_ts_bleed_moves_stray_text_to_next_column():
    labels = ["Lap", "T/SBackStretch", "Turn 1"]
    assert repair_ts_bleed(labels) == ["Lap", "T/S", "BackStretch Turn 1"]


def test_repair_ts_bleed_noop_when_already_clean():
    labels = ["Lap", "T/S", "Turn 1"]
    assert repair_ts_bleed(labels) == ["Lap", "T/S", "Turn 1"]


def test_repair_split_lap_header_strips_bleed_and_keeps_lap():
    labels = ["Sect L", "Lap", "Turn 1"]
    assert repair_split_lap_header(labels) == ["Sect", "Lap", "Turn 1"]


def test_repair_split_lap_header_normalizes_spaced_lap_label():
    labels = ["Sect", "L ap", "Turn 1"]
    assert repair_split_lap_header(labels) == ["Sect", "Lap", "Turn 1"]


def test_repair_turn_entry_split_merges_turn_and_entry():
    labels = ["T/S", "Turn 1", "EntryBackStretch"]
    assert repair_turn_entry_split(labels) == ["T/S", "Turn 1 Entry", "BackStretch"]


def test_find_lap_time_index_finds_lap_label():
    labels = ["Sect", "T/S", "Turn 1", "Lap", "PI to PO"]
    assert find_lap_time_index(labels) == 3


def test_find_lap_time_index_falls_back_to_before_pit_label():
    labels = ["Sect", "T/S", "Turn 1", "PI to PO"]
    assert find_lap_time_index(labels) == 2


def test_find_lap_time_index_none_when_no_lap_or_pit_label():
    labels = ["Sect", "T/S", "Turn 1", "Turn 2"]
    assert find_lap_time_index(labels) is None


def test_column_roles_splits_sections_and_pits_around_lap_time():
    labels = ["Sect", "T/S", "Turn 1", "Lap", "PI to PO"]
    roles = column_roles(labels)
    assert roles["section_labels"] == ["Turn 1"]
    assert roles["section_idxs"] == [2]
    assert roles["lap_time_idx"] == 3
    assert roles["pit_labels"] == ["PI to PO"]
    assert roles["pit_idxs"] == [4]


def test_column_roles_no_lap_time_treats_rest_as_sections():
    labels = ["Sect", "T/S", "Turn 1", "Turn 2"]
    roles = column_roles(labels)
    assert roles["lap_time_idx"] is None
    assert roles["section_labels"] == ["Turn 1", "Turn 2"]
    assert roles["section_idxs"] == [2, 3]
    assert roles["pit_labels"] == []
    assert roles["pit_idxs"] == []


def test_clean_time_extracts_value_when_header_text_bleeds_into_cell():
    # Real-world example: a "Stretch 5" column header bleeds into its own
    # data cell instead of being detected as a header word.
    assert clean_time("Stretch 5\n2.8407") == "2.8407"
    assert clean_time("1\n2.4112") == "2.4112"


def test_clean_time_still_handles_plain_values():
    assert clean_time("38.4405") == "38.4405"
    assert clean_time("") == ""
    assert clean_time(None) == ""
