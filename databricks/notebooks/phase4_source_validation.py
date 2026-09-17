# Databricks notebook source
"""Fail-fast validation of the exact approved landed Core V1 source revisions."""

import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = dbutils.widgets.get("bundle_root")
os.environ["EV_CATALOG"] = dbutils.widgets.get("catalog")
os.environ["EV_VOLUME_ROOT"] = dbutils.widgets.get("volume_root")
sys.path.insert(0, f"{PROJECT_ROOT}/src")

from ev_charging.bronze_ingestion import landing_path
from ev_charging.identity import sha256_file, source_revision_id
from ev_charging.source_contracts import inspect_bnetza, inspect_destatis, inspect_kba


INSPECTORS = {"bnetza": inspect_bnetza, "kba": inspect_kba, "destatis": inspect_destatis}
config = json.loads(Path(f"{PROJECT_ROOT}/config/source_revisions_v1.json").read_text(encoding="utf-8"))
results = []

for source in config["sources"]:
    if source["classification"] != "CORE_V1":
        continue

    path = Path(landing_path(source))
    if not path.is_file():
        raise FileNotFoundError(f"Approved landed source is missing: {path}")

    observed_size = path.stat().st_size
    observed_sha256 = sha256_file(path)
    if observed_size != source["size_bytes"]:
        raise ValueError(
            f"{source['provider']} landed size {observed_size} != approved {source['size_bytes']}"
        )
    if observed_sha256 != source["sha256"]:
        raise ValueError(
            f"{source['provider']} landed SHA-256 {observed_sha256} != approved {source['sha256']}"
        )

    observed = INSPECTORS[source["provider"]](path, source["expected_reference_date"])
    results.append(
        {
            "provider": source["provider"],
            "source_revision_id": source_revision_id(
                source["provider"],
                source["dataset_id"],
                source["expected_reference_date"],
                observed_sha256,
            ),
            "reference_date": observed["reference_date"],
            "row_grain": observed["row_grain"],
            "required_columns_present": observed["required_columns_present"],
            "observed_sha256": observed_sha256,
            "observed_size_bytes": observed_size,
        }
    )

if len(results) != 3:
    raise ValueError(f"Expected three Core V1 source revisions, observed {len(results)}")

dbutils.notebook.exit(
    json.dumps(
        {
            "action": "VALIDATE",
            "result": "PASS",
            "core_v1_source_count": len(results),
            "sources": results,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
