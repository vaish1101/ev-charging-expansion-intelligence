import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_governed_mapping_evidence_hashes_and_current_crosswalk():
    config = json.loads((ROOT / "config/geography_rules_v1.json").read_text(encoding="utf-8"))
    for section in ("bnetza_district_mapping", "destatis_analysis_region_bridge"):
        evidence = ROOT / config[section]["evidence_path"]
        assert hashlib.sha256(evidence.read_bytes()).hexdigest() == config[section]["evidence_sha256"]

    evidence = ROOT / config["bnetza_district_mapping"]["evidence_path"]
    selected = [
        row
        for row in _rows(evidence)
        if row["source_reference"] == "BNetzA 2026-09-01"
        and row["target_reference"] == "2026-06-30"
        and row["matched"] == "True"
    ]
    unique = {(row["Bundesland"], row["source_district_label"]): row["matched_district_key"] for row in selected}
    assert len(unique) == 401
    assert unique[("Hessen", "Kreisfreie Stadt Hanau")] == "06415"


def test_actual_401_to_400_bridge_and_only_trier_many_to_one():
    config = json.loads((ROOT / "config/geography_rules_v1.json").read_text(encoding="utf-8"))
    bridge = _rows(ROOT / config["destatis_analysis_region_bridge"]["evidence_path"])
    assert len(bridge) == 401
    assert len({row["source_district_key"] for row in bridge}) == 401
    assert len({row["target_analysis_region_key"] for row in bridge}) == 400
    target_counts = Counter(row["target_analysis_region_key"] for row in bridge)
    assert {key: count for key, count in target_counts.items() if count > 1} == {"07211": 2}
    trier_sources = {
        row["source_district_key"]
        for row in bridge
        if row["target_analysis_region_key"] == "07211"
    }
    assert trier_sources == {"07211", "07235"}
    hanau = next(row for row in bridge if row["source_district_key"] == "06415")
    assert hanau["valid_from"] == "2026-01-01"

