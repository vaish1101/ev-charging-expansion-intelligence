# Databricks notebook source
"""Block workflow completion unless the governed published serving layer is ready."""

import json
import sys


PROJECT_ROOT = dbutils.widgets.get("bundle_root")
CATALOG = dbutils.widgets.get("catalog")
sys.path.insert(0, f"{PROJECT_ROOT}/src")

from ev_charging.identity import date_set_id


manifest = json.loads(
    open(f"{PROJECT_ROOT}/config/date_set_manifest_core_v1.json", encoding="utf-8").read()
)
DATE_SET_ID, _ = date_set_id(manifest)


quality_rows = spark.sql(
    f"""
    SELECT date_set_id, publication_state, power_bi_refresh_ready,
           passed_dq_checks, failed_dq_checks, gold_run_id,
           kba_reference_date, bnetza_reference_date, destatis_reference_date,
           kba_to_bnetza_lag_days
    FROM {CATALOG}.gold.vw_powerbi_date_set_quality
    WHERE date_set_id = '{DATE_SET_ID}'
    """
).collect()
if len(quality_rows) != 1:
    raise ValueError(f"Expected one published quality row, observed {len(quality_rows)}")

quality = quality_rows[0].asDict(recursive=True)
expected_quality = {
    "publication_state": "published",
    "power_bi_refresh_ready": True,
    "passed_dq_checks": 73,
    "failed_dq_checks": 0,
    "kba_to_bnetza_lag_days": 62,
}
for field, expected in expected_quality.items():
    if quality[field] != expected:
        raise ValueError(f"Serving quality field {field}={quality[field]!r}, expected {expected!r}")

summary = spark.sql(
    f"""
    SELECT
      COUNT(*) AS analysis_regions,
      SUM(registered_bev_passenger_car_stock) AS registered_bevs,
      SUM(registered_passenger_car_stock) AS registered_passenger_cars,
      SUM(in_service_registered_charging_facilities) AS in_service_facilities,
      SUM(in_service_registered_charging_points) AS in_service_points,
      SUM(in_service_registered_normal_charging_points) AS in_service_normal_points,
      SUM(in_service_registered_fast_charging_points) AS in_service_fast_points,
      SUM(in_service_registered_unclassified_charging_points) AS in_service_unclassified_points,
      CAST(SUM(in_service_registered_facility_nominal_power_kw) AS DECIMAL(20,3)) AS registered_nominal_power_kw
    FROM {CATALOG}.gold.vw_powerbi_region_kpi_published
    WHERE date_set_id = '{DATE_SET_ID}'
    """
).first().asDict(recursive=True)

expected_summary = {
    "analysis_regions": 400,
    "registered_bevs": 2362218,
    "registered_passenger_cars": 49644855,
    "in_service_facilities": 116423,
    "in_service_points": 209098,
    "in_service_normal_points": 154702,
    "in_service_fast_points": 54396,
    "in_service_unclassified_points": 0,
    "registered_nominal_power_kw": 9086313.500,
}
for field, expected in expected_summary.items():
    if float(summary[field]) != float(expected):
        raise ValueError(f"Serving metric {field}={summary[field]!r}, expected {expected!r}")

dbutils.notebook.exit(
    json.dumps(
        {
            "action": "SERVING_READINESS",
            "result": "PASS",
            "date_set_id": DATE_SET_ID,
            "gold_run_id": quality["gold_run_id"],
            "quality": {key: str(value) for key, value in quality.items()},
            "summary": {key: str(value) for key, value in summary.items()},
        },
        sort_keys=True,
    )
)
