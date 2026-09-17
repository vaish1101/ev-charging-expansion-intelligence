import json
from decimal import Decimal
from pathlib import Path

import pytest

from ev_charging.gold_rules import (
    candidate_publication_action,
    denominator_quality_reason,
    operational_supply,
    ratio_or_none,
    scaffold_supply,
    validate_kpi_contracts,
)


ROOT = Path(__file__).resolve().parents[1]


def test_machine_readable_contract_is_exactly_the_approved_twelve_kpis():
    config = json.loads((ROOT / "config/kpi_contract_v1.json").read_text(encoding="utf-8"))
    validate_kpi_contracts(config)
    assert [item["id"] for item in config["kpis"]] == [f"KPI-{number:02d}" for number in range(1, 13)]


def test_ratio_precision_rounding_and_zero_null_policy():
    assert ratio_or_none(1, 6, 1000) == Decimal("166.6667")
    assert ratio_or_none(1, 6, 100) == Decimal("16.6667")
    assert ratio_or_none(0, 6, 1000) == Decimal("0.0000")
    assert ratio_or_none(1, 0, 1000) is None
    assert ratio_or_none(None, 5, 1000) is None
    assert denominator_quality_reason(0) == "invalid_denominator"
    assert denominator_quality_reason(None) == "invalid_denominator"
    assert denominator_quality_reason(1) is None


def test_maintenance_is_excluded_from_every_operational_numerator():
    rows = [
        {"is_in_service": True, "points": 2, "power_kw": "44.0"},
        {"is_in_service": False, "points": 38, "power_kw": "484.0"},
    ]
    assert operational_supply(rows) == {
        "facilities": 1,
        "points": 2,
        "power_kw": Decimal("44.0"),
    }


def test_zero_supply_region_is_left_preserved():
    assert scaffold_supply(["a", "b"], {"a": {"facilities": 1, "points": 2, "power_kw": "22"}}) == [
        {"analysis_region_code": "a", "facilities": 1, "points": 2, "power_kw": Decimal("22")},
        {"analysis_region_code": "b", "facilities": 0, "points": 0, "power_kw": Decimal("0")},
    ]


def test_candidate_publication_and_idempotency_states():
    assert candidate_publication_action("candidate", 0, 400, False) == "PUBLISH"
    assert candidate_publication_action("published", 400, 400, True) == "NO_OP"
    with pytest.raises(ValueError):
        candidate_publication_action("published", 399, 400, True)

