from datetime import date
from decimal import Decimal

import pytest

from ev_charging.silver_rules import (
    active_on,
    classify_point,
    facility_equation,
    is_in_service,
    key_set_equal,
    normalize_geography_text,
    overlapping_keys,
    parse_german_decimal,
    parse_nonnegative_integer,
    point_equation,
    populated_point_slots,
    preserve_region_scaffold,
    stable_identifier,
    unresolved_dates,
)


def test_conservative_normalization_is_deterministic():
    assert normalize_geography_text("  Kreisfreie   Stadt München ") == "kreisfreie stadt muenchen"
    assert normalize_geography_text("Straße / Örtlich") == "strasse oertlich"


def test_effective_date_boundaries_are_inclusive_start_exclusive_end():
    boundary = date(2026, 1, 1)
    assert active_on(date(1, 1, 1), boundary, date(2025, 12, 31))
    assert not active_on(date(1, 1, 1), boundary, boundary)
    assert active_on(boundary, None, boundary)


def test_overlap_and_gap_checks():
    clean = [
        {"key": "hanau", "valid_from": date(1, 1, 1), "valid_to": date(2026, 1, 1)},
        {"key": "hanau", "valid_from": date(2026, 1, 1), "valid_to": None},
    ]
    assert overlapping_keys(clean, ["key"]) == []
    assert unresolved_dates(clean, ["key"], [(('hanau',), date(2026, 1, 1))]) == []
    overlap = clean + [{"key": "hanau", "valid_from": date(2025, 12, 31), "valid_to": None}]
    assert overlapping_keys(overlap, ["key"]) == [("hanau",)]
    assert unresolved_dates(clean, ["key"], [(('other',), date(2026, 1, 1))]) == [
        (("other",), date(2026, 1, 1), 0)
    ]


def test_hanau_pre_post_mapping_is_data_driven():
    rows = [
        {"code": "06435014", "district": "06435", "valid_from": date(1, 1, 1), "valid_to": date(2026, 1, 1)},
        {"code": "06415000", "district": "06415", "valid_from": date(2026, 1, 1), "valid_to": None},
    ]
    assert [r["district"] for r in rows if active_on(r["valid_from"], r["valid_to"], date(2025, 12, 31))] == ["06435"]
    assert [r["district"] for r in rows if active_on(r["valid_from"], r["valid_to"], date(2026, 1, 1))] == ["06415"]


def test_trier_two_to_one_and_kba_key_equality():
    bridge = {"07211": "07211", "07235": "07211", "01001": "01001"}
    assert bridge["07211"] == bridge["07235"] == "07211"
    assert key_set_equal(set(bridge.values()), {"07211", "01001"})


def test_status_is_exact_equivalence():
    assert is_in_service("In Betrieb")
    assert not is_in_service("In Wartung")
    assert not is_in_service("in betrieb")
    assert not is_in_service("In Betrieb ")


def test_numeric_typing_does_not_turn_markers_into_zero():
    assert parse_german_decimal("1.234,5") == Decimal("1234.5")
    assert parse_nonnegative_integer("123") == 123
    for marker in ("", ".", "-", "/", None):
        with pytest.raises(ValueError):
            parse_nonnegative_integer(marker)


def test_point_slot_normalization_and_classification():
    row = {
        "steckertypen1": "Type 2; CCS",
        "nennleistung_stecker1": "22; 50",
        "steckertypen2": "Type 2",
        "nennleistung_stecker2": "11",
        "steckertypen3": "",
    }
    points = populated_point_slots(row)
    assert len(points) == 2
    assert points[0]["point_class"] == "FAST"
    assert points[1]["point_class"] == "NORMAL"
    assert classify_point(()) == "UNCLASSIFIED"


def test_point_parent_and_reconciliation_equations():
    facilities = {"f1", "f2"}
    points = [{"parent": "f1"}, {"parent": "f2"}]
    assert all(point["parent"] in facilities for point in points)
    assert point_equation(8, 5, 2, 1)
    assert facility_equation(7, 6, 1)


def test_zero_supply_region_preservation():
    scaffold = preserve_region_scaffold(["a", "b", "c"], {"a": 2, "c": 1})
    assert scaffold == [("a", 2), ("b", 0), ("c", 1)]


def test_deterministic_identity_supports_idempotent_rerun():
    assert stable_identifier("ar", "07211", "2026-06-30", "v1") == stable_identifier(
        "ar", "07211", "2026-06-30", "v1"
    )
    assert stable_identifier("ar", "07211", "2026-06-30", "v1") != stable_identifier(
        "ar", "07235", "2026-06-30", "v1"
    )
