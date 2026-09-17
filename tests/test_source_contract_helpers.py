from decimal import Decimal

import pytest

from ev_charging.bronze_ingestion import (
    idempotent_action,
    quarantine_balances,
    raw_excel_text,
    safe_column_name,
)
from ev_charging.source_contracts import (
    destatis_district_code,
    normalize_excel_code,
    parse_german_decimal,
    parse_nonnegative_integer,
    point_max_power,
    point_slot_populated,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("22", Decimal("22")), ("22,5", Decimal("22.5")), ("1.234,500", Decimal("1234.500"))],
)
def test_german_decimal_parser(raw, expected):
    assert parse_german_decimal(raw) == expected


@pytest.mark.parametrize("raw", ["", "1,2,3", "1 234,5", "12.34", "-1", None])
def test_german_decimal_parser_rejects_ambiguous_values(raw):
    with pytest.raises(ValueError):
        parse_german_decimal(raw)


def test_bnetza_populated_slot_and_point_max_contract():
    assert point_slot_populated(" CCS ")
    assert not point_slot_populated("  ")
    assert not point_slot_populated(None)
    assert point_max_power("11; 22,5;22,5") == Decimal("22.5")


def test_kba_key_normalization_and_integer_rules():
    assert normalize_excel_code("06415", 5) == "06415"
    assert normalize_excel_code(6415.0, 5) == "06415"
    assert parse_nonnegative_integer(0) == 0
    assert parse_nonnegative_integer("25035") == 25035
    with pytest.raises(ValueError):
        parse_nonnegative_integer("2,5")


def test_destatis_district_key_construction_preserves_widths():
    assert destatis_district_code("06", 4, "15") == "06415"


def test_physical_names_and_raw_excel_values_are_stable():
    assert safe_column_name("Nennleistung Ladeeinrichtung [kW]") == "nennleistung_ladeeinrichtung_kw"
    assert safe_column_name("Straße") == "strasse"
    assert raw_excel_text(None) == ""
    assert raw_excel_text(11000.0) == "11000"
    assert raw_excel_text("/") == "/"


def test_idempotency_decision():
    assert idempotent_action(0, 400) == "INGEST"
    assert idempotent_action(400, 400) == "NO_OP"
    with pytest.raises(ValueError):
        idempotent_action(399, 400)


def test_quarantine_accounting():
    assert quarantine_balances(400, 400, 0)
    assert quarantine_balances(400, 399, 1)
    assert not quarantine_balances(400, 399, 0)
