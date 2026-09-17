#!/usr/bin/env python3
"""Validate the locked Core V1 controls in a deployed catalog."""

from __future__ import annotations

import argparse
import json
import re

from bootstrap_databricks import execute


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--catalog", default="ev_analytics")
    args = parser.parse_args()
    if not IDENTIFIER.fullmatch(args.catalog):
        raise ValueError("Catalog must be a simple Unity Catalog identifier")

    # execute() deliberately prints only a public-safe label. The serving
    # readiness task independently validates the same exact controls and fails
    # the workflow on any mismatch.
    catalog = f"`{args.catalog}`"
    expected = {
        "regions": 400,
        "registered_bevs": 2362218,
        "registered_passenger_cars": 49644855,
        "facilities": 116423,
        "points": 209098,
        "normal_points": 154702,
        "fast_points": 54396,
        "nominal_power_kw": "9086313.500",
        "passed_checks": 73,
        "failed_checks": 0,
    }
    conditions = " AND ".join(
        [
            "regions = 400",
            "registered_bevs = 2362218",
            "registered_passenger_cars = 49644855",
            "facilities = 116423",
            "points = 209098",
            "normal_points = 154702",
            "fast_points = 54396",
            "nominal_power_kw = CAST(9086313.500 AS DECIMAL(18,3))",
            "passed_checks = 73",
            "failed_checks = 0",
        ]
    )
    sql = f"""
    WITH controls AS (
      SELECT
        COUNT(*) AS regions,
        SUM(registered_bev_passenger_car_stock) AS registered_bevs,
        SUM(registered_passenger_car_stock) AS registered_passenger_cars,
        SUM(in_service_registered_charging_facilities) AS facilities,
        SUM(in_service_registered_charging_points) AS points,
        SUM(in_service_registered_normal_charging_points) AS normal_points,
        SUM(in_service_registered_fast_charging_points) AS fast_points,
        CAST(SUM(in_service_registered_facility_nominal_power_kw) AS DECIMAL(18,3)) AS nominal_power_kw
      FROM {catalog}.gold.vw_powerbi_region_kpi_published
    ), quality AS (
      SELECT passed_dq_checks AS passed_checks, failed_dq_checks AS failed_checks
      FROM {catalog}.gold.vw_powerbi_date_set_quality
      WHERE publication_state = 'published' AND power_bi_refresh_ready = true
      ORDER BY completed_at DESC LIMIT 1
    )
    SELECT assert_true({conditions}, 'Locked Gold controls did not reconcile')
    FROM controls CROSS JOIN quality
    """
    execute(args.profile, args.warehouse_id, sql, "locked Gold controls")
    print(json.dumps({"result": "PASS", "controls": expected}, indent=2))


if __name__ == "__main__":
    main()
