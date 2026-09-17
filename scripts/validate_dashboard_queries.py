#!/usr/bin/env python3
"""Execute every source-controlled AI/BI dashboard dataset query.

The script deliberately uses the Databricks CLI profile rather than accepting a
token. This keeps credentials out of arguments, logs, and repository artifacts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"}


def run_cli(profile: str, *args: str) -> dict[str, Any]:
    command = ["databricks", *args, "--profile", profile, "--output", "json"]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def execute_query(
    *, profile: str, warehouse_id: str, catalog: str, schema: str, statement: str
) -> dict[str, Any]:
    payload = {
        "warehouse_id": warehouse_id,
        "catalog": catalog,
        "schema": schema,
        "wait_timeout": "50s",
        "on_wait_timeout": "CONTINUE",
        "disposition": "INLINE",
        "statement": statement,
    }
    response = run_cli(
        profile,
        "api",
        "post",
        "/api/2.0/sql/statements",
        "--json",
        json.dumps(payload),
    )
    statement_id = response["statement_id"]

    for _ in range(35):
        state = response["status"]["state"]
        if state in TERMINAL_STATES:
            return response
        time.sleep(2)
        response = run_cli(
            profile,
            "api",
            "get",
            f"/api/2.0/sql/statements/{statement_id}",
        )

    raise TimeoutError(f"Statement {statement_id} did not finish within 120 seconds")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dashboard",
        type=Path,
        default=Path(".bundle_artifacts/ev_charging_intelligence.lvdash.json"),
    )
    parser.add_argument("--profile", default="ev-express")
    parser.add_argument("--warehouse-id", required=True, help="SQL Warehouse ID in your own workspace")
    parser.add_argument("--catalog", default="ev_analytics")
    parser.add_argument("--schema", default="gold")
    args = parser.parse_args()

    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    results = []

    for dataset in dashboard["datasets"]:
        response = execute_query(
            profile=args.profile,
            warehouse_id=args.warehouse_id,
            catalog=args.catalog,
            schema=args.schema,
            statement="\n".join(dataset["queryLines"]),
        )
        status = response["status"]
        entry = {
            "dataset": dataset["name"],
            "state": status["state"],
            "error": status.get("error"),
            "row_count": response.get("manifest", {}).get("total_row_count"),
        }
        results.append(entry)
        if status["state"] != "SUCCEEDED":
            print(json.dumps({"results": results}, indent=2))
            return 1

    print(json.dumps({"results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
