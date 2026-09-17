# Databricks notebook source
"""Thin entry point for Phase 2B immutable landing to Bronze ingestion."""

import json
import os
import sys


PROJECT_ROOT = dbutils.widgets.get("bundle_root")
os.environ["EV_CATALOG"] = dbutils.widgets.get("catalog")
os.environ["EV_VOLUME_ROOT"] = dbutils.widgets.get("volume_root")
sys.path.insert(0, f"{PROJECT_ROOT}/src")

from ev_charging.bronze_ingestion import run_phase2b


result = run_phase2b(
    spark,
    f"{PROJECT_ROOT}/config/source_revisions_v1.json",
    f"{PROJECT_ROOT}/config/date_set_manifest_core_v1.json",
)
dbutils.notebook.exit(json.dumps(result, ensure_ascii=False, sort_keys=True))
