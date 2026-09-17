# Databricks notebook source
"""Synthetic dependency/import gate for the source-controlled Phase 2B package."""

import json
import os
import sys


PROJECT_ROOT = dbutils.widgets.get("bundle_root")
os.environ["EV_CATALOG"] = dbutils.widgets.get("catalog")
sys.path.insert(0, f"{PROJECT_ROOT}/src")

import openpyxl

from ev_charging.identity import date_set_id
from ev_charging.source_contracts import parse_german_decimal


identifier, canonical = date_set_id({"z": None, "a": "value"})
assert identifier.startswith("ds_") and len(identifier) == 67
assert canonical == '{"a":"value","z":null}'
assert str(parse_german_decimal("1.234,5")) == "1234.5"

dbutils.notebook.exit(
    json.dumps(
        {
            "openpyxl_version": openpyxl.__version__,
            "source_controlled_module_import": "passed",
            "strict_parser_import": "passed",
        },
        sort_keys=True,
    )
)
