"""Pure Phase 2D Gold KPI and publication rules."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


RATIO_QUANTUM = Decimal("0.0001")
EXPECTED_KPI_IDS = tuple(f"KPI-{number:02d}" for number in range(1, 13))


def ratio_or_none(numerator: Any, denominator: Any, multiplier: Any) -> Decimal | None:
    """Apply the frozen ratio null policy and half-up four-decimal rounding."""
    if numerator is None or denominator is None:
        return None
    numerator_decimal = Decimal(str(numerator))
    denominator_decimal = Decimal(str(denominator))
    if denominator_decimal <= 0:
        return None
    return (
        Decimal(str(multiplier)) * numerator_decimal / denominator_decimal
    ).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def denominator_quality_reason(denominator: Any) -> str | None:
    if denominator is None:
        return "invalid_denominator"
    return "invalid_denominator" if Decimal(str(denominator)) <= 0 else None


def validate_kpi_contracts(config: Mapping[str, Any]) -> None:
    kpis = config.get("kpis", [])
    ids = tuple(item.get("id") for item in kpis)
    if ids != EXPECTED_KPI_IDS:
        raise ValueError(f"KPI contract must contain KPI-01 through KPI-12 in order; observed {ids}")
    if len({item["column"] for item in kpis}) != 12:
        raise ValueError("KPI output columns must be unique")
    if config.get("ratio_rounding") != "ROUND_HALF_UP" or config.get("ratio_scale") != 4:
        raise ValueError("KPI ratio precision contract changed")
    kpi12 = kpis[-1]
    if kpi12["unit"] != "kW per 1,000 BEVs":
        raise ValueError("KPI-12 unit must be exactly 'kW per 1,000 BEVs'")
    prohibited = ("score", "rank", "roi", "forecast", "capacity")
    for item in kpis:
        haystack = " ".join(str(value) for value in item.values()).casefold()
        if any(term in haystack for term in prohibited):
            raise ValueError(f"Unapproved KPI terminology in {item['id']}")


def operational_supply(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate synthetic facility rows with exact maintenance exclusion."""
    eligible = [row for row in rows if row["is_in_service"] is True]
    return {
        "facilities": len(eligible),
        "points": sum(int(row["points"]) for row in eligible),
        "power_kw": sum((Decimal(str(row["power_kw"])) for row in eligible), Decimal("0")),
    }


def candidate_publication_action(
    registry_state: str,
    existing_rows: int,
    expected_rows: int,
    fingerprint_matches: bool,
) -> str:
    if registry_state == "candidate" and existing_rows == 0:
        return "PUBLISH"
    if registry_state == "published" and existing_rows == expected_rows and fingerprint_matches:
        return "NO_OP"
    raise ValueError("Gold publication state conflicts with immutable date-set contract")


def scaffold_supply(region_codes: Iterable[str], supply: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "analysis_region_code": code,
            "facilities": int(supply.get(code, {}).get("facilities", 0)),
            "points": int(supply.get(code, {}).get("points", 0)),
            "power_kw": Decimal(str(supply.get(code, {}).get("power_kw", 0))),
        }
        for code in region_codes
    ]

