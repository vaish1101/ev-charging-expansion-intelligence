#!/usr/bin/env python3
"""Create the Unity Catalog namespace required by the project.

Azure Databricks workspaces with account default storage can create catalogs
through SQL even when the Unity Catalog REST create-catalog endpoint rejects a
catalog without an explicit managed location. This idempotent bootstrap keeps
that workspace-specific concern outside the analytical pipeline.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def cli(profile: str, *args: str) -> dict:
    command = ["databricks", *args, "--profile", profile, "--output", "json"]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def execute(profile: str, warehouse_id: str, sql: str, label: str) -> None:
    body = json.dumps(
        {
            "warehouse_id": warehouse_id,
            "statement": sql,
            "wait_timeout": "50s",
            "on_wait_timeout": "CONTINUE",
        }
    )
    result = cli(profile, "api", "post", "/api/2.0/sql/statements", "--json", body)
    state = result.get("status", {}).get("state")
    statement_id = result.get("statement_id")
    while state in {"PENDING", "RUNNING"}:
        if not statement_id:
            raise RuntimeError(f"{label}: missing statement identifier while {state}")
        time.sleep(2)
        result = cli(
            profile,
            "api",
            "get",
            f"/api/2.0/sql/statements/{statement_id}",
        )
        state = result.get("status", {}).get("state")
    if state != "SUCCEEDED":
        message = result.get("status", {}).get("error", {}).get("message", "unknown error")
        raise RuntimeError(f"{label} failed: {message}")
    print(f"OK: {label}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the project catalog, schemas and managed raw-source Volume."
    )
    parser.add_argument("--profile", required=True, help="Databricks CLI profile")
    parser.add_argument("--warehouse-id", required=True, help="SQL Warehouse ID")
    parser.add_argument("--catalog", default="ev_analytics")
    args = parser.parse_args()

    if not IDENTIFIER.fullmatch(args.catalog):
        raise ValueError("Catalog must be a simple Unity Catalog identifier")
    catalog = f"`{args.catalog}`"

    statements = [
        ("catalog", f"CREATE CATALOG IF NOT EXISTS {catalog}"),
        *[
            (
                f"{schema} schema",
                f"CREATE SCHEMA IF NOT EXISTS {catalog}.`{schema}`",
            )
            for schema in ("landing", "bronze", "silver", "gold", "audit")
        ],
        (
            "raw source Volume",
            f"CREATE VOLUME IF NOT EXISTS {catalog}.`landing`.`raw_sources`",
        ),
    ]
    for label, statement in statements:
        execute(args.profile, args.warehouse_id, statement, label)
    print("Databricks namespace bootstrap completed")


if __name__ == "__main__":
    main()
