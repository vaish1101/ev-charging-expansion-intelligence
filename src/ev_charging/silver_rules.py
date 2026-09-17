"""Pure Phase 2C Silver semantic and reconciliation rules.

This module deliberately contains no Spark dependency so the contract logic can be
tested locally and reused by the Databricks transformation entry point.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence


IN_SERVICE_STATUS = "In Betrieb"
MAINTENANCE_STATUS = "In Wartung"
POINT_CLASS_NORMAL = "NORMAL"
POINT_CLASS_FAST = "FAST"
POINT_CLASS_UNCLASSIFIED = "UNCLASSIFIED"


def normalize_geography_text(value: str) -> str:
    """Apply the approved conservative normalization used by governed bridges."""
    text = unicodedata.normalize("NFKC", value or "").strip().casefold()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def active_on(valid_from: date, valid_to: date | None, reference_date: date) -> bool:
    """Return true for the approved inclusive-start/exclusive-end interval."""
    return valid_from <= reference_date and (valid_to is None or reference_date < valid_to)


def interval_overlaps(
    left_from: date,
    left_to: date | None,
    right_from: date,
    right_to: date | None,
) -> bool:
    """Return whether two inclusive-start/exclusive-end date intervals overlap."""
    return (right_to is None or left_from < right_to) and (left_to is None or right_from < left_to)


def overlapping_keys(
    records: Iterable[Mapping[str, Any]],
    key_fields: Sequence[str],
) -> list[tuple[Any, ...]]:
    """Return keys with at least one overlapping effective-dated record pair."""
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for record in records:
        key = tuple(record[field] for field in key_fields)
        grouped.setdefault(key, []).append(record)
    failures: list[tuple[Any, ...]] = []
    for key, values in grouped.items():
        ordered = sorted(values, key=lambda item: item["valid_from"])
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if interval_overlaps(left["valid_from"], left.get("valid_to"), right["valid_from"], right.get("valid_to")):
                    failures.append(key)
                    break
            if failures and failures[-1] == key:
                break
    return failures


def unresolved_dates(
    records: Iterable[Mapping[str, Any]],
    key_fields: Sequence[str],
    required: Iterable[tuple[tuple[Any, ...], date]],
) -> list[tuple[tuple[Any, ...], date, int]]:
    """Return required key/dates with anything other than one active mapping."""
    materialized = list(records)
    failures = []
    for key, reference_date in required:
        matches = [
            row
            for row in materialized
            if tuple(row[field] for field in key_fields) == key
            and active_on(row["valid_from"], row.get("valid_to"), reference_date)
        ]
        if len(matches) != 1:
            failures.append((key, reference_date, len(matches)))
    return failures


def is_in_service(status: str) -> bool:
    """Apply exact, case-sensitive operational eligibility semantics."""
    return status == IN_SERVICE_STATUS


def parse_german_decimal(value: Any) -> Decimal:
    """Parse an official German-formatted number without treating markers as zero."""
    if value is None:
        raise ValueError("required numeric value is null")
    text = str(value).strip()
    if not text or text in {".", "-", "/"}:
        raise ValueError(f"numeric disclosure marker or blank: {text!r}")
    normalized = text.replace("\u00a0", "").replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        result = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"invalid numeric value: {text!r}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite numeric value: {text!r}")
    return result


def parse_nonnegative_integer(value: Any) -> int:
    number = parse_german_decimal(value)
    if number < 0 or number != number.to_integral_value():
        raise ValueError(f"expected non-negative integer, observed {value!r}")
    return int(number)


def parse_positive_power_tokens(value: Any) -> tuple[Decimal, ...]:
    """Parse ordered positive kW tokens from a populated point-power source cell."""
    if value is None or not str(value).strip():
        return ()
    # The approved BNetzA contract uses semicolons between ratings; commas are
    # decimal separators and therefore must never be treated as delimiters.
    tokens = [token.strip() for token in str(value).split(";") if token.strip()]
    parsed = tuple(parse_german_decimal(token) for token in tokens)
    if any(number <= 0 for number in parsed):
        raise ValueError(f"point power tokens must be positive: {value!r}")
    return parsed


def connector_tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(token.strip() for token in str(value).split(";") if token.strip())


def classify_point(powers_kw: Sequence[Decimal]) -> str:
    if not powers_kw:
        return POINT_CLASS_UNCLASSIFIED
    return POINT_CLASS_FAST if max(powers_kw) > Decimal("22") else POINT_CLASS_NORMAL


def populated_point_slots(row: Mapping[str, Any], slots: int = 6) -> list[dict[str, Any]]:
    """Normalize populated source slots; one connector cell means one point row."""
    points = []
    for slot in range(1, slots + 1):
        connector_value = row.get(f"steckertypen{slot}")
        if connector_value is None or not str(connector_value).strip():
            continue
        powers = parse_positive_power_tokens(row.get(f"nennleistung_stecker{slot}"))
        points.append(
            {
                "point_slot": slot,
                "connector_types": connector_tokens(connector_value),
                "connector_power_kw": powers,
                "point_max_nominal_power_kw": max(powers) if powers else None,
                "point_class": classify_point(powers),
            }
        )
    return points


def point_equation(total: int, normal: int, fast: int, unclassified: int) -> bool:
    return total == normal + fast + unclassified


def facility_equation(total: int, in_service: int, non_in_service: int) -> bool:
    return total == in_service + non_in_service


def preserve_region_scaffold(
    region_codes: Iterable[str],
    supply_counts: Mapping[str, int],
) -> list[tuple[str, int]]:
    """Left-preserve the governed analysis-region set for reconciliation."""
    return [(code, int(supply_counts.get(code, 0))) for code in region_codes]


def key_set_equal(left: Iterable[str], right: Iterable[str]) -> bool:
    return set(left) == set(right)


def duplicate_values(values: Iterable[Any]) -> list[Any]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def stable_identifier(prefix: str, *parts: Any) -> str:
    encoded = "\x1f".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
