# Databricks notebook source
"""Copy the three approved immutable source revisions into the managed Volume."""

import json
import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = dbutils.widgets.get("bundle_root")
CATALOG = dbutils.widgets.get("catalog")
VOLUME_ROOT = dbutils.widgets.get("volume_root")
os.environ["EV_CATALOG"] = CATALOG
os.environ["EV_VOLUME_ROOT"] = VOLUME_ROOT
sys.path.insert(0, f"{PROJECT_ROOT}/src")

from ev_charging.bronze_ingestion import landing_path, manifest_landing_path
from ev_charging.identity import date_set_id, sha256_file


config_path = Path(f"{PROJECT_ROOT}/config/source_revisions_v1.json")
manifest_path = Path(f"{PROJECT_ROOT}/config/date_set_manifest_core_v1.json")
config = json.loads(config_path.read_text(encoding="utf-8"))
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
results = []

for source in config["sources"]:
    if source["classification"] != "CORE_V1":
        continue
    source_path = Path(f"{PROJECT_ROOT}/{source['filename']}")
    if not source_path.is_file():
        raise FileNotFoundError(
            f"Approved source is absent from the deployed bundle: {source['filename']}"
        )
    if source_path.stat().st_size != source["size_bytes"] or sha256_file(source_path) != source["sha256"]:
        raise ValueError(f"Local approved source bytes do not match the frozen contract: {source_path}")

    destination = Path(landing_path(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    action = "NO_OP"
    if not destination.is_file():
        shutil.copyfile(source_path, destination)
        action = "COPIED"
    if destination.stat().st_size != source["size_bytes"] or sha256_file(destination) != source["sha256"]:
        raise ValueError(f"Landed source bytes do not match the frozen contract: {destination}")
    results.append({"provider": source["provider"], "action": action, "landing_path": str(destination)})

identifier, _ = date_set_id(manifest)
manifest_destination = Path(manifest_landing_path(identifier))
manifest_destination.parent.mkdir(parents=True, exist_ok=True)
if not manifest_destination.is_file():
    shutil.copyfile(manifest_path, manifest_destination)
if manifest_destination.read_bytes() != manifest_path.read_bytes():
    raise ValueError("Landed date-set manifest differs from the source-controlled manifest")

dbutils.notebook.exit(
    json.dumps(
        {
            "action": "IMMUTABLE_SOURCE_LANDING",
            "result": "PASS",
            "source_count": len(results),
            "sources": results,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
