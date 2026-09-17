# Databricks notebook source
"""Thin source-controlled entry point for Phase 2D Gold publication."""

import json
import os
import sys


PROJECT_ROOT = dbutils.widgets.get("bundle_root")
os.environ["EV_CATALOG"] = dbutils.widgets.get("catalog")
sys.path.insert(0, f"{PROJECT_ROOT}/src")

from ev_charging.gold_transformations import run_phase2d


result = run_phase2d(
    spark,
    f"{PROJECT_ROOT}/config/date_set_manifest_core_v1.json",
    f"{PROJECT_ROOT}/config/kpi_contract_v1.json",
)
dbutils.notebook.exit(json.dumps(result, ensure_ascii=False, sort_keys=True))
