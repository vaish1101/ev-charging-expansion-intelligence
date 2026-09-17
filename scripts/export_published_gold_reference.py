#!/usr/bin/env python3
"""Export compact public Gold references and recreatable serving-view DDL.

The script uses an authenticated Databricks CLI profile. It never persists
statement IDs, warehouse IDs, workspace URLs, credentials, or account details.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"}


def cli(profile: str, *args: str) -> dict[str, Any]:
    result = subprocess.run(
        ["databricks", *args, "--profile", profile, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def execute(profile: str, warehouse_id: str, statement: str) -> dict[str, Any]:
    payload = {
        "warehouse_id": warehouse_id,
        "wait_timeout": "50s",
        "on_wait_timeout": "CONTINUE",
        "disposition": "INLINE",
        "format": "JSON_ARRAY",
        "statement": statement,
    }
    response = cli(
        profile,
        "api",
        "post",
        "/api/2.0/sql/statements",
        "--json",
        json.dumps(payload),
    )
    statement_id = response["statement_id"]
    for _ in range(90):
        state = response["status"]["state"]
        if state in TERMINAL_STATES:
            if state != "SUCCEEDED":
                raise RuntimeError(response["status"].get("error", state))
            return response
        time.sleep(2)
        response = cli(
            profile,
            "api",
            "get",
            f"/api/2.0/sql/statements/{statement_id}",
        )
    raise TimeoutError("SQL statement did not complete within three minutes")


def rows(response: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    columns = [item["name"] for item in response["manifest"]["schema"]["columns"]]
    data = response.get("result", {}).get("data_array", [])
    return columns, data


def write_csv(path: Path, columns: list[str], data: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="ev-express")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--catalog", default="ev_analytics")
    args = parser.parse_args()

    region_view = f"{args.catalog}.gold.vw_powerbi_region_kpi_published"
    quality_view = f"{args.catalog}.gold.vw_powerbi_date_set_quality"

    region_response = execute(
        args.profile,
        args.warehouse_id,
        f"SELECT * FROM {region_view} ORDER BY analysis_region_code",
    )
    quality_response = execute(
        args.profile,
        args.warehouse_id,
        f"SELECT * FROM {quality_view} ORDER BY completed_at DESC",
    )
    region_columns, region_rows = rows(region_response)
    quality_columns, quality_rows = rows(quality_response)
    write_csv(ROOT / "data/reference/regional_kpi_snapshot.csv", region_columns, region_rows)
    write_csv(ROOT / "data/reference/dataset_quality.csv", quality_columns, quality_rows)

    ddl_blocks = []
    for view in (region_view, quality_view):
        ddl_response = execute(
            args.profile,
            args.warehouse_id,
            f"SHOW CREATE TABLE {view}",
        )
        _, ddl_rows = rows(ddl_response)
        if len(ddl_rows) != 1 or len(ddl_rows[0]) != 1:
            raise RuntimeError(f"Unexpected SHOW CREATE TABLE result for {view}")
        ddl_blocks.append(str(ddl_rows[0][0]).rstrip(";") + ";")

    ddl_path = ROOT / "databricks/sql/published_gold_views.sql"
    ddl_path.write_text(
        "-- Recreates the two public Gold serving views used by the dashboards.\n"
        "-- Generated from the final published Databricks definitions.\n\n"
        + "\n\n".join(ddl_blocks)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "regional_rows": len(region_rows),
                "quality_rows": len(quality_rows),
                "view_definitions": len(ddl_blocks),
            }
        )
    )


if __name__ == "__main__":
    main()
