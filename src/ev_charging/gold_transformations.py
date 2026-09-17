"""Phase 2D governed Gold aggregation, validation and publication."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ev_charging.gold_rules import validate_kpi_contracts
from ev_charging.identity import canonical_json, date_set_id
from ev_charging.runtime import catalog_name
from ev_charging.silver_rules import stable_identifier


CATALOG = catalog_name()
SILVER = f"{CATALOG}.silver"
GOLD = f"{CATALOG}.gold"
AUDIT = f"{CATALOG}.audit"

SILVER_TABLES = {
    "region": f"{SILVER}.dim_analysis_region",
    "stock": f"{SILVER}.fact_ev_stock",
    "facility": f"{SILVER}.fact_charging_facility_snapshot",
    "point": f"{SILVER}.fact_charging_point_snapshot",
}

GOLD_TABLES = {
    "ev_stock": f"{GOLD}.gold_ev_stock_region",
    "supply": f"{GOLD}.gold_charging_supply_region",
    "kpi": f"{GOLD}.gold_region_kpi_snapshot",
}

CANDIDATE_TABLES = {
    "ev_stock": f"{AUDIT}.candidate_gold_ev_stock_region",
    "supply": f"{AUDIT}.candidate_gold_charging_supply_region",
    "kpi": f"{AUDIT}.candidate_gold_region_kpi_snapshot",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _append_dict(spark: Any, table: str, row: dict[str, Any]) -> None:
    schema = spark.table(table).schema
    spark.createDataFrame(
        [tuple(row.get(field.name) for field in schema.fields)], schema
    ).write.format("delta").mode("append").saveAsTable(table)


def ensure_gold_audit_tables(spark: Any) -> None:
    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.gold_publication_run (
          gold_run_id STRING, date_set_id STRING, started_at TIMESTAMP,
          candidate_created_at TIMESTAMP, validated_at TIMESTAMP, published_at TIMESTAMP,
          completed_at TIMESTAMP, status STRING, action STRING, failure_reason STRING,
          candidate_fingerprints_json STRING, published_fingerprints_json STRING,
          passed_dq_checks BIGINT, failed_dq_checks BIGINT
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.gold_dq_result (
          gold_run_id STRING, date_set_id STRING, check_id STRING, check_name STRING,
          expected STRING, observed STRING, result STRING, blocking BOOLEAN,
          affected_count BIGINT, checked_at TIMESTAMP
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.gold_entity_revision (
          gold_entity_revision_id STRING, entity_name STRING, destination_table STRING,
          date_set_id STRING, row_count BIGINT, content_fingerprint STRING,
          source_context_json STRING, published_at TIMESTAMP
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.gold_reconciliation_region (
          gold_run_id STRING, date_set_id STRING, analysis_region_sk STRING,
          analysis_region_code STRING,
          gold_bev_stock BIGINT, silver_bev_stock BIGINT, bev_stock_pass BOOLEAN,
          gold_in_service_facilities BIGINT, silver_in_service_facilities BIGINT,
          facility_count_pass BOOLEAN,
          gold_in_service_points BIGINT, silver_in_service_points BIGINT, point_count_pass BOOLEAN,
          gold_in_service_normal_points BIGINT, silver_in_service_normal_points BIGINT,
          normal_point_count_pass BOOLEAN,
          gold_in_service_fast_points BIGINT, silver_in_service_fast_points BIGINT,
          fast_point_count_pass BOOLEAN,
          gold_in_service_unclassified_points BIGINT, silver_in_service_unclassified_points BIGINT,
          unclassified_point_count_pass BOOLEAN,
          gold_in_service_registered_facility_nominal_power_kw DECIMAL(20,3),
          silver_in_service_registered_facility_nominal_power_kw DECIMAL(20,3),
          nominal_power_pass BOOLEAN, all_measures_pass BOOLEAN, reconciled_at TIMESTAMP
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.gold_sample_recomputation (
          gold_run_id STRING, date_set_id STRING, sample_role STRING,
          analysis_region_code STRING, analysis_region_name STRING,
          gold_bev_stock BIGINT, recomputed_bev_stock BIGINT,
          gold_in_service_facilities BIGINT, recomputed_in_service_facilities BIGINT,
          gold_in_service_points BIGINT, recomputed_in_service_points BIGINT,
          gold_in_service_fast_points BIGINT, recomputed_in_service_fast_points BIGINT,
          gold_in_service_registered_facility_nominal_power_kw DECIMAL(20,3),
          recomputed_in_service_registered_facility_nominal_power_kw DECIMAL(20,3),
          gold_points_per_1000_bevs DECIMAL(18,4),
          recomputed_points_per_1000_bevs DECIMAL(18,4),
          all_checks_pass BOOLEAN, checked_at TIMESTAMP
        ) USING DELTA
        """,
    ]
    for statement in statements:
        spark.sql(statement)


def _assertion(
    checks: list[dict[str, Any]],
    check_id: str,
    name: str,
    expected: Any,
    observed: Any,
    affected_count: int = 0,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "check_name": name,
            "expected": str(expected),
            "observed": str(observed),
            "result": "PASS" if observed == expected else "FAIL",
            "blocking": True,
            "affected_count": int(affected_count),
        }
    )


def _publish_checks(
    spark: Any,
    run_id: str,
    identifier: str,
    checks: Iterable[dict[str, Any]],
    checked_at: datetime,
) -> None:
    for check in checks:
        _append_dict(
            spark,
            f"{AUDIT}.gold_dq_result",
            {
                "gold_run_id": run_id,
                "date_set_id": identifier,
                "checked_at": checked_at,
                **check,
            },
        )


def _fingerprint(frame: Any, excluded: set[str] | None = None) -> tuple[int, str]:
    from pyspark.sql import functions as F

    excluded = excluded or set()
    columns = sorted(column for column in frame.columns if column not in excluded)
    row_json = F.to_json(
        F.struct(*[F.col(column) for column in columns]), {"ignoreNullFields": "false"}
    )
    hashed = frame.select(
        F.sha2(row_json, 256).alias("sha"), F.xxhash64(row_json).alias("xx")
    )
    summary = hashed.agg(
        F.count("*").alias("rows"),
        F.sum(F.col("xx").cast("decimal(38,0)")).alias("xx_sum"),
        F.min("sha").alias("min_sha"),
        F.max("sha").alias("max_sha"),
    ).first()
    payload = {
        "rows": int(summary["rows"]),
        "xx_sum": str(summary["xx_sum"] or 0),
        "min_sha": summary["min_sha"],
        "max_sha": summary["max_sha"],
    }
    return payload["rows"], hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _ratio(numerator: Any, denominator: Any, multiplier: int) -> Any:
    from pyspark.sql import functions as F

    expression = (
        F.lit(multiplier).cast("decimal(38,10)")
        * numerator.cast("decimal(38,10)")
        / denominator.cast("decimal(38,10)")
    )
    return F.when(
        denominator.isNull() | (denominator <= 0) | numerator.isNull(),
        F.lit(None).cast("decimal(18,4)"),
    ).otherwise(F.round(expression, 4).cast("decimal(18,4)"))


def _lineage_columns(manifest: dict[str, Any], created_at: datetime) -> list[Any]:
    from pyspark.sql import functions as F

    return [
        F.lit("2026-07-01").cast("date").alias("kba_reference_date"),
        F.lit("2026-09-01").cast("date").alias("bnetza_reference_date"),
        F.lit("2026-06-30").cast("date").alias("destatis_reference_date"),
        F.lit(62).cast("int").alias("kba_to_bnetza_lag_days"),
        F.lit(manifest["kba_source_revision_id"]).alias("kba_source_revision_id"),
        F.lit(manifest["bnetza_source_revision_id"]).alias("bnetza_source_revision_id"),
        F.lit(manifest["destatis_geography_source_revision_id"]).alias(
            "destatis_geography_source_revision_id"
        ),
        F.lit(manifest["bnetza_district_mapping_version"]).alias(
            "bnetza_district_mapping_version"
        ),
        F.lit(manifest["district_analysis_region_bridge_version"]).alias(
            "district_analysis_region_bridge_version"
        ),
        F.lit(manifest["transformation_rule_version"]).alias(
            "transformation_rule_version"
        ),
        F.lit(manifest["kpi_definition_version"]).alias("kpi_definition_version"),
        F.lit(created_at).cast("timestamp").alias("published_at"),
    ]


def _silver_inputs(spark: Any, manifest: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    from pyspark.sql import functions as F

    regions = spark.table(SILVER_TABLES["region"]).where(
        (F.col("mapping_version") == manifest["district_analysis_region_bridge_version"])
        & F.col("is_current")
    )
    stock = spark.table(SILVER_TABLES["stock"]).where(
        F.col("source_revision_id") == manifest["kba_source_revision_id"]
    )
    facilities = spark.table(SILVER_TABLES["facility"]).where(
        F.col("source_revision_id") == manifest["bnetza_source_revision_id"]
    )
    points = spark.table(SILVER_TABLES["point"]).where(
        F.col("source_revision_id") == manifest["bnetza_source_revision_id"]
    )
    return regions, stock, facilities, points


def _demand_aggregate(stock: Any) -> Any:
    from pyspark.sql import functions as F

    return stock.groupBy("analysis_region_sk", "analysis_region_code").agg(
        F.sum("bev_passenger_car_stock").cast("bigint").alias("registered_bev_passenger_car_stock"),
        F.sum("total_passenger_car_stock").cast("bigint").alias("registered_passenger_car_stock"),
        F.sum("plugin_hybrid_passenger_car_stock").cast("bigint").alias(
            "plugin_hybrid_passenger_car_stock"
        ),
    )


def _supply_aggregate(facilities: Any, points: Any) -> Any:
    from pyspark.sql import functions as F

    facility_aggregate = facilities.groupBy("analysis_region_sk", "analysis_region_code").agg(
        F.countDistinct("facility_id").alias("all_status_registered_charging_facilities"),
        F.countDistinct(F.when(F.col("is_in_service"), F.col("facility_id"))).alias(
            "in_service_registered_charging_facilities"
        ),
        F.countDistinct(F.when(F.col("status") == "In Wartung", F.col("facility_id"))).alias(
            "maintenance_registered_charging_facilities"
        ),
        F.countDistinct(
            F.when(~F.col("status").isin("In Betrieb", "In Wartung"), F.col("facility_id"))
        ).alias("other_status_registered_charging_facilities"),
        F.sum("registered_facility_nominal_power_kw").cast("decimal(20,3)").alias(
            "all_status_registered_facility_nominal_power_kw"
        ),
        F.sum(
            F.when(F.col("is_in_service"), F.col("registered_facility_nominal_power_kw")).otherwise(0)
        ).cast("decimal(20,3)").alias("in_service_registered_facility_nominal_power_kw"),
        F.sum(
            F.when(F.col("status") == "In Wartung", F.col("registered_facility_nominal_power_kw")).otherwise(0)
        ).cast("decimal(20,3)").alias("maintenance_registered_facility_nominal_power_kw"),
        F.sum(
            F.when(
                ~F.col("status").isin("In Betrieb", "In Wartung"),
                F.col("registered_facility_nominal_power_kw"),
            ).otherwise(0)
        ).cast("decimal(20,3)").alias("other_status_registered_facility_nominal_power_kw"),
    )
    eligible_points = points.alias("p").join(
        facilities.select(
            "charging_facility_snapshot_sk",
            F.col("status").alias("parent_status"),
            F.col("is_in_service").alias("parent_is_in_service"),
            F.col("analysis_region_sk").alias("parent_analysis_region_sk"),
        ).alias("f"),
        "charging_facility_snapshot_sk",
        "inner",
    )
    point_aggregate = eligible_points.groupBy(
        F.col("p.analysis_region_sk").alias("analysis_region_sk"),
        F.col("p.analysis_region_code").alias("analysis_region_code"),
    ).agg(
        F.count("*").alias("all_status_registered_charging_points"),
        F.sum(F.col("parent_is_in_service").cast("bigint")).alias(
            "in_service_registered_charging_points"
        ),
        F.sum(
            (F.col("parent_is_in_service") & (F.col("point_class") == "NORMAL")).cast("bigint")
        ).alias("in_service_registered_normal_charging_points"),
        F.sum(
            (F.col("parent_is_in_service") & (F.col("point_class") == "FAST")).cast("bigint")
        ).alias("in_service_registered_fast_charging_points"),
        F.sum(
            (F.col("parent_is_in_service") & (F.col("point_class") == "UNCLASSIFIED")).cast("bigint")
        ).alias("in_service_registered_unclassified_charging_points"),
        F.sum((F.col("parent_status") == "In Wartung").cast("bigint")).alias(
            "maintenance_registered_charging_points"
        ),
        F.sum(
            (~F.col("parent_status").isin("In Betrieb", "In Wartung")).cast("bigint")
        ).alias("other_status_registered_charging_points"),
    )
    return facility_aggregate.join(
        point_aggregate, ["analysis_region_sk", "analysis_region_code"], "full"
    )


def _build_candidates(
    regions: Any,
    stock: Any,
    facilities: Any,
    points: Any,
    identifier: str,
    manifest: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    from pyspark.sql import functions as F

    scaffold = regions.select(
        "analysis_region_sk", "analysis_region_code", "analysis_region_name"
    )
    demand_source = _demand_aggregate(stock)
    supply_source = _supply_aggregate(facilities, points)
    demand = scaffold.join(
        demand_source, ["analysis_region_sk", "analysis_region_code"], "left"
    )
    total_pkw = F.col("registered_passenger_car_stock")
    demand = demand.select(
        F.lit(identifier).alias("date_set_id"),
        "analysis_region_sk", "analysis_region_code", "analysis_region_name",
        "registered_bev_passenger_car_stock", "registered_passenger_car_stock",
        "plugin_hybrid_passenger_car_stock",
        _ratio(F.col("registered_bev_passenger_car_stock"), total_pkw, 100).alias(
            "bev_penetration_percent"
        ),
        F.when(total_pkw.isNull() | (total_pkw <= 0), "invalid_denominator")
        .otherwise(F.lit(None).cast("string"))
        .alias("pkw_denominator_quality_reason"),
        *_lineage_columns(manifest, created_at),
    )

    count_columns = [
        "all_status_registered_charging_facilities",
        "in_service_registered_charging_facilities",
        "maintenance_registered_charging_facilities",
        "other_status_registered_charging_facilities",
        "all_status_registered_charging_points",
        "in_service_registered_charging_points",
        "in_service_registered_normal_charging_points",
        "in_service_registered_fast_charging_points",
        "in_service_registered_unclassified_charging_points",
        "maintenance_registered_charging_points",
        "other_status_registered_charging_points",
    ]
    power_columns = [
        "all_status_registered_facility_nominal_power_kw",
        "in_service_registered_facility_nominal_power_kw",
        "maintenance_registered_facility_nominal_power_kw",
        "other_status_registered_facility_nominal_power_kw",
    ]
    supply = scaffold.join(
        supply_source, ["analysis_region_sk", "analysis_region_code"], "left"
    )
    for column in count_columns:
        supply = supply.withColumn(column, F.coalesce(F.col(column), F.lit(0).cast("bigint")))
    for column in power_columns:
        supply = supply.withColumn(
            column, F.coalesce(F.col(column), F.lit(0).cast("decimal(20,3)"))
        )
    supply = supply.select(
        F.lit(identifier).alias("date_set_id"),
        "analysis_region_sk", "analysis_region_code", "analysis_region_name",
        *count_columns, *power_columns,
        F.lit(0).cast("bigint").alias("silver_quarantine_records"),
        *_lineage_columns(manifest, created_at),
    )

    joined = demand.alias("d").join(
        supply.alias("s"), ["date_set_id", "analysis_region_sk", "analysis_region_code", "analysis_region_name"]
    )
    bev = F.col("d.registered_bev_passenger_car_stock")
    kpi = joined.select(
        "date_set_id", "analysis_region_sk", "analysis_region_code", "analysis_region_name",
        bev.alias("registered_bev_passenger_car_stock"),
        F.col("d.registered_passenger_car_stock"),
        F.col("d.bev_penetration_percent"),
        F.col("s.in_service_registered_charging_facilities"),
        F.col("s.in_service_registered_charging_points"),
        F.col("s.in_service_registered_normal_charging_points"),
        F.col("s.in_service_registered_fast_charging_points"),
        F.col("s.in_service_registered_unclassified_charging_points"),
        F.col("s.in_service_registered_facility_nominal_power_kw"),
        _ratio(F.col("s.in_service_registered_charging_points"), bev, 1000).alias(
            "in_service_registered_charging_points_per_1000_bevs"
        ),
        _ratio(F.col("s.in_service_registered_fast_charging_points"), bev, 1000).alias(
            "in_service_registered_fast_charging_points_per_1000_bevs"
        ),
        _ratio(F.col("s.in_service_registered_charging_facilities"), bev, 1000).alias(
            "in_service_registered_charging_facilities_per_1000_bevs"
        ),
        _ratio(F.col("s.in_service_registered_facility_nominal_power_kw"), bev, 1000).alias(
            "in_service_registered_facility_nominal_power_kw_per_1000_bevs"
        ),
        F.when(bev.isNull() | (bev <= 0), "invalid_denominator")
        .otherwise(F.lit(None).cast("string"))
        .alias("bev_denominator_quality_reason"),
        F.lit("kW per 1,000 BEVs").alias("kpi_12_unit"),
        F.lit("VALIDATED").alias("quality_status"),
        F.col("d.kba_reference_date"), F.col("d.bnetza_reference_date"),
        F.col("d.destatis_reference_date"), F.col("d.kba_to_bnetza_lag_days"),
        F.col("d.kba_source_revision_id"), F.col("d.bnetza_source_revision_id"),
        F.col("d.destatis_geography_source_revision_id"),
        F.col("d.bnetza_district_mapping_version"),
        F.col("d.district_analysis_region_bridge_version"),
        F.col("d.transformation_rule_version"), F.col("d.kpi_definition_version"),
        F.col("d.published_at"),
    )
    return {"ev_stock": demand, "supply": supply, "kpi": kpi}


def _verify_manifest_registry(
    spark: Any, manifest: dict[str, Any], expected_identifier: str, checks: list[dict[str, Any]]
) -> str:
    identifier, canonical = date_set_id(manifest)
    _assertion(checks, "REV-001", "canonical manifest date_set_id", expected_identifier, identifier)
    registry_rows = spark.table(f"{AUDIT}.date_set_registry").where(
        f"date_set_id = {_sql_literal(identifier)}"
    ).collect()
    _assertion(checks, "REV-002", "date-set registry row count", 1, len(registry_rows))
    if len(registry_rows) != 1:
        return "missing"
    row = registry_rows[0]
    _assertion(
        checks,
        "REV-003",
        "canonical manifest registry equality",
        canonical,
        row["canonical_manifest_json"],
    )
    _assertion(
        checks,
        "REV-004",
        "date-set registry state eligible for build",
        True,
        row["state"] in {"candidate", "validated", "failed", "published"},
    )
    return row["state"]


def _independent_reconciliation_source(stock: Any, facilities: Any, points: Any) -> Any:
    """Recompute regional controls from Silver in a separate plan from Gold candidates."""
    return _demand_aggregate(stock).join(
        _supply_aggregate(facilities, points),
        ["analysis_region_sk", "analysis_region_code"],
        "full",
    )


def _regional_reconciliation(
    candidates: dict[str, Any],
    independent: Any,
    run_id: str,
    identifier: str,
    checked_at: datetime,
) -> Any:
    from pyspark.sql import functions as F

    gold = candidates["kpi"].alias("g")
    silver = independent.alias("s")
    joined = gold.join(
        silver,
        (F.col("g.analysis_region_sk") == F.col("s.analysis_region_sk"))
        & (F.col("g.analysis_region_code") == F.col("s.analysis_region_code")),
        "full",
    )
    comparisons = {
        "bev_stock_pass": F.col("g.registered_bev_passenger_car_stock").eqNullSafe(
            F.col("s.registered_bev_passenger_car_stock")
        ),
        "facility_count_pass": F.col("g.in_service_registered_charging_facilities").eqNullSafe(
            F.col("s.in_service_registered_charging_facilities")
        ),
        "point_count_pass": F.col("g.in_service_registered_charging_points").eqNullSafe(
            F.col("s.in_service_registered_charging_points")
        ),
        "normal_point_count_pass": F.col(
            "g.in_service_registered_normal_charging_points"
        ).eqNullSafe(F.col("s.in_service_registered_normal_charging_points")),
        "fast_point_count_pass": F.col(
            "g.in_service_registered_fast_charging_points"
        ).eqNullSafe(F.col("s.in_service_registered_fast_charging_points")),
        "unclassified_point_count_pass": F.col(
            "g.in_service_registered_unclassified_charging_points"
        ).eqNullSafe(F.col("s.in_service_registered_unclassified_charging_points")),
        "nominal_power_pass": F.col(
            "g.in_service_registered_facility_nominal_power_kw"
        ).eqNullSafe(F.col("s.in_service_registered_facility_nominal_power_kw")),
    }
    all_pass = None
    for comparison in comparisons.values():
        all_pass = comparison if all_pass is None else all_pass & comparison
    return joined.select(
        F.lit(run_id).alias("gold_run_id"), F.lit(identifier).alias("date_set_id"),
        F.coalesce(F.col("g.analysis_region_sk"), F.col("s.analysis_region_sk")).alias(
            "analysis_region_sk"
        ),
        F.coalesce(F.col("g.analysis_region_code"), F.col("s.analysis_region_code")).alias(
            "analysis_region_code"
        ),
        F.col("g.registered_bev_passenger_car_stock").alias("gold_bev_stock"),
        F.col("s.registered_bev_passenger_car_stock").alias("silver_bev_stock"),
        comparisons["bev_stock_pass"].alias("bev_stock_pass"),
        F.col("g.in_service_registered_charging_facilities").alias(
            "gold_in_service_facilities"
        ),
        F.col("s.in_service_registered_charging_facilities").alias(
            "silver_in_service_facilities"
        ),
        comparisons["facility_count_pass"].alias("facility_count_pass"),
        F.col("g.in_service_registered_charging_points").alias("gold_in_service_points"),
        F.col("s.in_service_registered_charging_points").alias("silver_in_service_points"),
        comparisons["point_count_pass"].alias("point_count_pass"),
        F.col("g.in_service_registered_normal_charging_points").alias(
            "gold_in_service_normal_points"
        ),
        F.col("s.in_service_registered_normal_charging_points").alias(
            "silver_in_service_normal_points"
        ),
        comparisons["normal_point_count_pass"].alias("normal_point_count_pass"),
        F.col("g.in_service_registered_fast_charging_points").alias(
            "gold_in_service_fast_points"
        ),
        F.col("s.in_service_registered_fast_charging_points").alias(
            "silver_in_service_fast_points"
        ),
        comparisons["fast_point_count_pass"].alias("fast_point_count_pass"),
        F.col("g.in_service_registered_unclassified_charging_points").alias(
            "gold_in_service_unclassified_points"
        ),
        F.col("s.in_service_registered_unclassified_charging_points").alias(
            "silver_in_service_unclassified_points"
        ),
        comparisons["unclassified_point_count_pass"].alias(
            "unclassified_point_count_pass"
        ),
        F.col("g.in_service_registered_facility_nominal_power_kw").alias(
            "gold_in_service_registered_facility_nominal_power_kw"
        ),
        F.col("s.in_service_registered_facility_nominal_power_kw").alias(
            "silver_in_service_registered_facility_nominal_power_kw"
        ),
        comparisons["nominal_power_pass"].alias("nominal_power_pass"),
        all_pass.alias("all_measures_pass"),
        F.lit(checked_at).cast("timestamp").alias("reconciled_at"),
    )


def _collect_controls_and_checks(
    spark: Any,
    manifest: dict[str, Any],
    kpi_config: dict[str, Any],
    regions: Any,
    stock: Any,
    facilities: Any,
    points: Any,
    candidates: dict[str, Any],
    regional: Any,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    from pyspark.sql import functions as F

    _assertion(checks, "REV-005", "KPI configuration version", manifest["kpi_definition_version"], kpi_config["kpi_definition_version"])
    _assertion(checks, "REV-006", "Silver analysis-region mapping version rows", 400, regions.count())
    _assertion(checks, "REV-007", "Silver KBA bound revision rows", 400, stock.count())
    _assertion(checks, "REV-008", "Silver BNetzA facility bound revision rows", 116443, facilities.count())
    _assertion(checks, "REV-009", "Silver BNetzA point bound revision rows", 209136, points.count())
    _assertion(checks, "REV-010", "deferred context source revision remains null", None, manifest["context_source_revision_id"])

    for entity, frame in candidates.items():
        rows = frame.count()
        keys = frame.select("date_set_id", "analysis_region_sk").distinct().count()
        mixed_ids = frame.where(F.col("date_set_id") != manifest_date_set_id(manifest)).count()
        _assertion(checks, f"GLD-{entity}-001", f"{entity} candidate rows", 400, rows)
        _assertion(checks, f"GLD-{entity}-002", f"{entity} unique business keys", 400, keys)
        _assertion(checks, f"GLD-{entity}-003", f"{entity} mixed date_set_id rows", 0, mixed_ids)
        orphan_regions = frame.select("analysis_region_sk").subtract(
            regions.select("analysis_region_sk")
        ).count()
        _assertion(
            checks,
            f"GLD-{entity}-004",
            f"{entity} analysis-region orphan rows",
            0,
            orphan_regions,
            orphan_regions,
        )

    demand = candidates["ev_stock"]
    demand_control = demand.agg(
        F.sum("registered_bev_passenger_car_stock").alias("bev"),
        F.sum("registered_passenger_car_stock").alias("pkw"),
        F.sum(F.col("registered_bev_passenger_car_stock").isNull().cast("bigint")).alias("null_bev"),
        F.sum((F.col("registered_bev_passenger_car_stock") < 0).cast("bigint")).alias("negative_bev"),
        F.sum((F.col("registered_passenger_car_stock") < F.col("registered_bev_passenger_car_stock")).cast("bigint")).alias("pkw_lt_bev"),
        F.sum((F.col("kba_to_bnetza_lag_days") != 62).cast("bigint")).alias("bad_lag"),
    ).first()
    silver_bev_total = stock.agg(F.sum("bev_passenger_car_stock")).first()[0]
    _assertion(checks, "DEM-001", "Gold national BEV equals Silver", silver_bev_total, demand_control["bev"])
    _assertion(checks, "DEM-002", "Gold null BEV rows", 0, demand_control["null_bev"])
    _assertion(checks, "DEM-003", "Gold negative BEV rows", 0, demand_control["negative_bev"])
    _assertion(checks, "DEM-004", "total passenger-car stock below BEV rows", 0, demand_control["pkw_lt_bev"])
    _assertion(checks, "DAT-001", "incorrect 62-day lag rows", 0, demand_control["bad_lag"])

    supply = candidates["supply"]
    supply_control = supply.agg(
        F.sum("all_status_registered_charging_facilities").alias("all_facilities"),
        F.sum("in_service_registered_charging_facilities").alias("in_service_facilities"),
        F.sum("maintenance_registered_charging_facilities").alias("maintenance_facilities"),
        F.sum("other_status_registered_charging_facilities").alias("other_facilities"),
        F.sum("all_status_registered_charging_points").alias("all_points"),
        F.sum("in_service_registered_charging_points").alias("in_service_points"),
        F.sum("in_service_registered_normal_charging_points").alias("normal_points"),
        F.sum("in_service_registered_fast_charging_points").alias("fast_points"),
        F.sum("in_service_registered_unclassified_charging_points").alias("unclassified_points"),
        F.sum("maintenance_registered_charging_points").alias("maintenance_points"),
        F.sum("other_status_registered_charging_points").alias("other_points"),
        F.sum("all_status_registered_facility_nominal_power_kw").alias("all_power"),
        F.sum("in_service_registered_facility_nominal_power_kw").alias("in_service_power"),
        F.sum("maintenance_registered_facility_nominal_power_kw").alias("maintenance_power"),
        F.sum("other_status_registered_facility_nominal_power_kw").alias("other_power"),
    ).first()
    _assertion(checks, "SUP-001", "all-status registered facilities", 116443, supply_control["all_facilities"])
    _assertion(checks, "SUP-002", "in-service registered facilities", 116423, supply_control["in_service_facilities"])
    _assertion(checks, "SUP-003", "maintenance registered facilities", 20, supply_control["maintenance_facilities"])
    _assertion(checks, "SUP-004", "other-status registered facilities", 0, supply_control["other_facilities"])
    _assertion(checks, "SUP-005", "all-status registered points", 209136, supply_control["all_points"])
    independently_computed_operational_points = points.alias("p").join(
        facilities.where(F.col("is_in_service")).select("charging_facility_snapshot_sk").alias("f"),
        "charging_facility_snapshot_sk",
        "inner",
    ).count()
    _assertion(checks, "SUP-006", "operational points independently recomputed from Silver", independently_computed_operational_points, supply_control["in_service_points"])
    _assertion(checks, "SUP-007", "operational point-class equation", supply_control["in_service_points"], supply_control["normal_points"] + supply_control["fast_points"] + supply_control["unclassified_points"])
    _assertion(checks, "SUP-008", "all versus operational/maintenance/other point equation", supply_control["all_points"], supply_control["in_service_points"] + supply_control["maintenance_points"] + supply_control["other_points"])
    _assertion(checks, "SUP-009", "all-status registered facility nominal power kW", "9086797.500", str(supply_control["all_power"]))
    _assertion(checks, "SUP-010", "in-service registered facility nominal power kW", "9086313.500", str(supply_control["in_service_power"]))
    _assertion(checks, "SUP-011", "maintenance registered facility nominal power kW", "484.000", str(supply_control["maintenance_power"]))
    _assertion(checks, "SUP-012", "power status equation", supply_control["all_power"], supply_control["in_service_power"] + supply_control["maintenance_power"] + supply_control["other_power"])
    regional_facility_equation_failures = supply.where(
        F.col("all_status_registered_charging_facilities")
        != F.col("in_service_registered_charging_facilities")
        + F.col("maintenance_registered_charging_facilities")
        + F.col("other_status_registered_charging_facilities")
    ).count()
    regional_point_equation_failures = supply.where(
        F.col("all_status_registered_charging_points")
        != F.col("in_service_registered_charging_points")
        + F.col("maintenance_registered_charging_points")
        + F.col("other_status_registered_charging_points")
    ).count()
    regional_power_equation_failures = supply.where(
        F.col("all_status_registered_facility_nominal_power_kw")
        != F.col("in_service_registered_facility_nominal_power_kw")
        + F.col("maintenance_registered_facility_nominal_power_kw")
        + F.col("other_status_registered_facility_nominal_power_kw")
    ).count()
    regional_class_equation_failures = supply.where(
        F.col("in_service_registered_charging_points")
        != F.col("in_service_registered_normal_charging_points")
        + F.col("in_service_registered_fast_charging_points")
        + F.col("in_service_registered_unclassified_charging_points")
    ).count()
    _assertion(checks, "SUP-013", "regional facility status-equation failures", 0, regional_facility_equation_failures, regional_facility_equation_failures)
    _assertion(checks, "SUP-014", "regional point status-equation failures", 0, regional_point_equation_failures, regional_point_equation_failures)
    _assertion(checks, "SUP-015", "regional nominal-power status-equation failures", 0, regional_power_equation_failures, regional_power_equation_failures)
    _assertion(checks, "SUP-016", "regional operational point-class equation failures", 0, regional_class_equation_failures, regional_class_equation_failures)
    regional_failures = regional.where(~F.col("all_measures_pass")).count()
    _assertion(checks, "REC-001", "regional Silver-to-Gold reconciliation failures", 0, regional_failures, regional_failures)
    _assertion(checks, "REC-002", "regional reconciliation rows", 400, regional.count())

    kpi = candidates["kpi"]
    ratio_columns = {
        "KPI-03": ("bev_penetration_percent", _ratio(F.col("registered_bev_passenger_car_stock"), F.col("registered_passenger_car_stock"), 100)),
        "KPI-09": ("in_service_registered_charging_points_per_1000_bevs", _ratio(F.col("in_service_registered_charging_points"), F.col("registered_bev_passenger_car_stock"), 1000)),
        "KPI-10": ("in_service_registered_fast_charging_points_per_1000_bevs", _ratio(F.col("in_service_registered_fast_charging_points"), F.col("registered_bev_passenger_car_stock"), 1000)),
        "KPI-11": ("in_service_registered_charging_facilities_per_1000_bevs", _ratio(F.col("in_service_registered_charging_facilities"), F.col("registered_bev_passenger_car_stock"), 1000)),
        "KPI-12": ("in_service_registered_facility_nominal_power_kw_per_1000_bevs", _ratio(F.col("in_service_registered_facility_nominal_power_kw"), F.col("registered_bev_passenger_car_stock"), 1000)),
    }
    for kpi_id, (column, expected_expression) in ratio_columns.items():
        mismatches = kpi.where(~F.col(column).eqNullSafe(expected_expression)).count()
        _assertion(checks, f"{kpi_id}-FORMULA", f"{kpi_id} exact formula mismatches", 0, mismatches, mismatches)
    field_types = {field.name: field.dataType.simpleString() for field in kpi.schema.fields}
    for contract in kpi_config["kpis"]:
        expected_type = contract["type"].casefold()
        observed_type = field_types[contract["column"]]
        _assertion(checks, f"{contract['id']}-TYPE", f"{contract['id']} output type", expected_type, observed_type)
    _assertion(checks, "KPI-12-UNIT", "KPI-12 unit rows", 0, kpi.where(F.col("kpi_12_unit") != "kW per 1,000 BEVs").count())
    lineage_failures = kpi.where(
        (F.col("kba_reference_date") != F.lit("2026-07-01").cast("date"))
        | (F.col("bnetza_reference_date") != F.lit("2026-09-01").cast("date"))
        | (F.col("destatis_reference_date") != F.lit("2026-06-30").cast("date"))
        | (F.col("kba_source_revision_id") != manifest["kba_source_revision_id"])
        | (F.col("bnetza_source_revision_id") != manifest["bnetza_source_revision_id"])
        | (F.col("destatis_geography_source_revision_id") != manifest["destatis_geography_source_revision_id"])
        | (F.col("bnetza_district_mapping_version") != manifest["bnetza_district_mapping_version"])
        | (F.col("district_analysis_region_bridge_version") != manifest["district_analysis_region_bridge_version"])
        | (F.col("transformation_rule_version") != manifest["transformation_rule_version"])
        | (F.col("kpi_definition_version") != manifest["kpi_definition_version"])
    ).count()
    _assertion(checks, "GLD-LIN-001", "Gold row-level lineage failures", 0, lineage_failures, lineage_failures)
    invalid_denominator_rows = kpi.where(F.col("registered_bev_passenger_car_stock") <= 0).count()
    invalid_reason_mismatches = kpi.where(
        (F.col("registered_bev_passenger_car_stock") <= 0)
        != (F.col("bev_denominator_quality_reason") == "invalid_denominator")
    ).count()
    _assertion(checks, "KPI-NULL-001", "invalid denominator reason mismatches", 0, invalid_reason_mismatches, invalid_reason_mismatches)
    _assertion(checks, "PUB-001", "Silver quarantine dependency rows", 0, spark.table(f"{AUDIT}.silver_quarantine").count())
    return {
        "national_bev_stock": int(demand_control["bev"]),
        "national_registered_passenger_car_stock": int(demand_control["pkw"]),
        "operational_facilities": int(supply_control["in_service_facilities"]),
        "operational_points": int(supply_control["in_service_points"]),
        "operational_normal_points": int(supply_control["normal_points"]),
        "operational_fast_points": int(supply_control["fast_points"]),
        "operational_unclassified_points": int(supply_control["unclassified_points"]),
        "operational_registered_facility_nominal_power_kw": str(supply_control["in_service_power"]),
        "maintenance_facilities_excluded": int(supply_control["maintenance_facilities"]),
        "maintenance_points_excluded": int(supply_control["maintenance_points"]),
        "maintenance_registered_facility_nominal_power_kw_excluded": str(supply_control["maintenance_power"]),
        "invalid_bev_denominator_regions": int(invalid_denominator_rows),
        "regional_reconciliation_failures": int(regional_failures),
    }


def manifest_date_set_id(manifest: dict[str, Any]) -> str:
    return date_set_id(manifest)[0]


def _sample_recomputation(
    spark: Any,
    candidates: dict[str, Any],
    independent: Any,
    run_id: str,
    identifier: str,
    checked_at: datetime,
) -> tuple[Any, list[dict[str, Any]]]:
    from pyspark.sql import functions as F
    from pyspark.sql.types import StringType, StructField, StructType

    supply = candidates["supply"]
    high_code = supply.orderBy(
        F.desc("in_service_registered_charging_points"), F.asc("analysis_region_code")
    ).select("analysis_region_code").first()[0]
    low_code = supply.orderBy(
        F.asc("in_service_registered_charging_points"), F.asc("analysis_region_code")
    ).select("analysis_region_code").first()[0]
    roles = [
        ("large_city", "11000"),
        ("ordinary_district", "09184"),
        ("trier_analysis_region", "07211"),
        ("hanau", "06415"),
        ("high_supply_qa_extreme", high_code),
        ("low_supply_qa_extreme", low_code),
    ]
    role_frame = spark.createDataFrame(
        roles,
        StructType(
            [
                StructField("sample_role", StringType(), False),
                StructField("analysis_region_code", StringType(), False),
            ]
        ),
    )
    gold = candidates["kpi"].alias("g")
    silver = independent.alias("s")
    joined = role_frame.alias("r").join(
        gold,
        F.col("r.analysis_region_code") == F.col("g.analysis_region_code"),
        "left",
    ).join(
        silver,
        F.col("r.analysis_region_code") == F.col("s.analysis_region_code"),
        "left",
    )
    recomputed_ratio = _ratio(
        F.col("s.in_service_registered_charging_points"),
        F.col("s.registered_bev_passenger_car_stock"),
        1000,
    )
    all_pass = (
        F.col("g.registered_bev_passenger_car_stock").eqNullSafe(
            F.col("s.registered_bev_passenger_car_stock")
        )
        & F.col("g.in_service_registered_charging_facilities").eqNullSafe(
            F.col("s.in_service_registered_charging_facilities")
        )
        & F.col("g.in_service_registered_charging_points").eqNullSafe(
            F.col("s.in_service_registered_charging_points")
        )
        & F.col("g.in_service_registered_fast_charging_points").eqNullSafe(
            F.col("s.in_service_registered_fast_charging_points")
        )
        & F.col("g.in_service_registered_facility_nominal_power_kw").eqNullSafe(
            F.col("s.in_service_registered_facility_nominal_power_kw")
        )
        & F.col("g.in_service_registered_charging_points_per_1000_bevs").eqNullSafe(
            recomputed_ratio
        )
    )
    evidence = joined.select(
        F.lit(run_id).alias("gold_run_id"), F.lit(identifier).alias("date_set_id"),
        F.col("r.sample_role"), F.col("r.analysis_region_code"),
        F.col("g.analysis_region_name"),
        F.col("g.registered_bev_passenger_car_stock").alias("gold_bev_stock"),
        F.col("s.registered_bev_passenger_car_stock").alias("recomputed_bev_stock"),
        F.col("g.in_service_registered_charging_facilities").alias(
            "gold_in_service_facilities"
        ),
        F.col("s.in_service_registered_charging_facilities").alias(
            "recomputed_in_service_facilities"
        ),
        F.col("g.in_service_registered_charging_points").alias("gold_in_service_points"),
        F.col("s.in_service_registered_charging_points").alias(
            "recomputed_in_service_points"
        ),
        F.col("g.in_service_registered_fast_charging_points").alias(
            "gold_in_service_fast_points"
        ),
        F.col("s.in_service_registered_fast_charging_points").alias(
            "recomputed_in_service_fast_points"
        ),
        F.col("g.in_service_registered_facility_nominal_power_kw").alias(
            "gold_in_service_registered_facility_nominal_power_kw"
        ),
        F.col("s.in_service_registered_facility_nominal_power_kw").alias(
            "recomputed_in_service_registered_facility_nominal_power_kw"
        ),
        F.col("g.in_service_registered_charging_points_per_1000_bevs").alias(
            "gold_points_per_1000_bevs"
        ),
        recomputed_ratio.alias("recomputed_points_per_1000_bevs"),
        all_pass.alias("all_checks_pass"),
        F.lit(checked_at).cast("timestamp").alias("checked_at"),
    )
    summaries = [
        {
            "sample_role": row["sample_role"],
            "analysis_region_code": row["analysis_region_code"],
            "analysis_region_name": row["analysis_region_name"],
            "bev_stock": row["gold_bev_stock"],
            "in_service_facilities": row["gold_in_service_facilities"],
            "in_service_points": row["gold_in_service_points"],
            "in_service_fast_points": row["gold_in_service_fast_points"],
            "in_service_registered_facility_nominal_power_kw": str(
                row["gold_in_service_registered_facility_nominal_power_kw"]
            ),
            "points_per_1000_bevs": str(row["gold_points_per_1000_bevs"]),
            "passed": row["all_checks_pass"],
        }
        for row in evidence.orderBy("sample_role").collect()
    ]
    return evidence, summaries


def _persist_candidates(
    frames: dict[str, Any], run_id: str, created_at: datetime
) -> None:
    from pyspark.sql import functions as F

    for entity, frame in frames.items():
        frame.withColumn("gold_run_id", F.lit(run_id)).withColumn(
            "candidate_status", F.lit("BUILT")
        ).withColumn(
            "candidate_created_at", F.lit(created_at).cast("timestamp")
        ).write.format("delta").mode("append").saveAsTable(CANDIDATE_TABLES[entity])


def _candidate_fingerprints(frames: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        entity: {
            "row_count": row_count,
            "content_fingerprint": fingerprint,
        }
        for entity, frame in frames.items()
        for row_count, fingerprint in [_fingerprint(frame, {"published_at"})]
    }


def _publish_gold_entities(
    spark: Any,
    frames: dict[str, Any],
    fingerprints: dict[str, dict[str, Any]],
    identifier: str,
    manifest: dict[str, Any],
    published_at: datetime,
) -> str:
    actions = []
    source_context = canonical_json(manifest)
    for entity, frame in frames.items():
        destination = GOLD_TABLES[entity]
        expected = fingerprints[entity]
        if spark.catalog.tableExists(destination):
            existing_frame = spark.table(destination).where(
                f"date_set_id = {_sql_literal(identifier)}"
            )
            existing_rows = existing_frame.count()
        else:
            existing_frame = None
            existing_rows = 0
        if existing_rows == 0:
            frame.write.format("delta").mode("append").saveAsTable(destination)
            action = "PUBLISH"
        elif existing_rows == expected["row_count"]:
            _, existing_fingerprint = _fingerprint(existing_frame, {"published_at"})
            if existing_fingerprint != expected["content_fingerprint"]:
                raise ValueError(f"Published Gold content conflict for {entity}")
            action = "NO_OP"
        else:
            raise ValueError(
                f"Partial Gold state for {entity}: {existing_rows}/{expected['row_count']} rows"
            )
        revision_id = stable_identifier("goldrev", entity, identifier)
        revision_rows = spark.table(f"{AUDIT}.gold_entity_revision").where(
            f"gold_entity_revision_id = {_sql_literal(revision_id)}"
        ).collect()
        if revision_rows:
            if (
                len(revision_rows) != 1
                or revision_rows[0]["row_count"] != expected["row_count"]
                or revision_rows[0]["content_fingerprint"] != expected["content_fingerprint"]
            ):
                raise ValueError(f"Immutable Gold entity-revision conflict for {entity}")
        else:
            _append_dict(
                spark,
                f"{AUDIT}.gold_entity_revision",
                {
                    "gold_entity_revision_id": revision_id,
                    "entity_name": entity,
                    "destination_table": destination,
                    "date_set_id": identifier,
                    "row_count": expected["row_count"],
                    "content_fingerprint": expected["content_fingerprint"],
                    "source_context_json": source_context,
                    "published_at": published_at,
                },
            )
        actions.append(action)
    if len(set(actions)) != 1:
        raise ValueError(f"Mixed Gold publication actions: {actions}")
    return actions[0]


def _create_serving_views(spark: Any) -> None:
    spark.sql(
        f"""
        CREATE OR REPLACE VIEW {GOLD}.vw_powerbi_region_kpi_published AS
        SELECT k.*, r.state AS publication_state, r.date_set_label
        FROM {GOLD_TABLES['kpi']} k
        INNER JOIN {AUDIT}.date_set_registry r USING (date_set_id)
        WHERE r.state = 'published'
        """
    )
    spark.sql(
        f"""
        CREATE OR REPLACE VIEW {GOLD}.vw_powerbi_date_set_quality AS
        WITH latest AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY date_set_id ORDER BY completed_at DESC, gold_run_id DESC
          ) AS row_number
          FROM {AUDIT}.gold_publication_run
          WHERE status = 'SUCCESS'
        )
        SELECT r.date_set_id, r.date_set_label, r.kba_reference_date,
               r.bnetza_reference_date, r.destatis_reference_date,
               r.state AS publication_state, l.gold_run_id,
               l.passed_dq_checks, l.failed_dq_checks, l.completed_at,
               CAST(62 AS INT) AS kba_to_bnetza_lag_days,
               CAST(l.failed_dq_checks = 0 AS BOOLEAN) AS power_bi_refresh_ready
        FROM {AUDIT}.date_set_registry r
        INNER JOIN latest l USING (date_set_id)
        WHERE r.state = 'published' AND l.row_number = 1
        """
    )


def _update_run(
    spark: Any,
    run_id: str,
    values: dict[str, Any],
) -> None:
    assignments = []
    for column, value in values.items():
        if value is None:
            literal = "NULL"
        elif isinstance(value, datetime):
            literal = f"TIMESTAMP {_sql_literal(value.isoformat(sep=' '))}"
        elif isinstance(value, (int, bool)):
            literal = str(value).upper()
        else:
            literal = _sql_literal(str(value))
        assignments.append(f"{column} = {literal}")
    spark.sql(
        f"UPDATE {AUDIT}.gold_publication_run SET {', '.join(assignments)} "
        f"WHERE gold_run_id = {_sql_literal(run_id)}"
    )


def run_phase2d(
    spark: Any,
    date_set_manifest_path: str,
    kpi_contract_path: str,
) -> dict[str, Any]:
    """Build, validate and publish the contracted Gold V1 regional layer."""
    manifest = _read_json(date_set_manifest_path)
    kpi_config = _read_json(kpi_contract_path)
    validate_kpi_contracts(kpi_config)
    identifier = manifest_date_set_id(manifest)
    expected_identifier = identifier
    run_id = str(uuid.uuid4())
    started = _utcnow()
    ensure_gold_audit_tables(spark)
    _append_dict(
        spark,
        f"{AUDIT}.gold_publication_run",
        {
            "gold_run_id": run_id,
            "date_set_id": identifier,
            "started_at": started,
            "status": "RUNNING",
            "action": "BUILD_CANDIDATE",
            "passed_dq_checks": 0,
            "failed_dq_checks": 0,
        },
    )
    staging_tables: list[str] = []
    registry_state = "missing"
    try:
        checks: list[dict[str, Any]] = []
        registry_state = _verify_manifest_registry(
            spark, manifest, expected_identifier, checks
        )
        if registry_state == "failed":
            spark.sql(
                f"UPDATE {AUDIT}.date_set_registry SET state = 'candidate' "
                f"WHERE date_set_id = {_sql_literal(identifier)} AND state = 'failed'"
            )
            registry_state = "candidate"
        regions, stock, facilities, points = _silver_inputs(spark, manifest)
        computed = _build_candidates(
            regions, stock, facilities, points, identifier, manifest, started
        )
        safe_run = run_id.replace("-", "")
        candidates = {}
        for entity, frame in computed.items():
            staging = f"{AUDIT}._phase2d_stage_{entity}_{safe_run}"
            frame.write.format("delta").mode("overwrite").saveAsTable(staging)
            staging_tables.append(staging)
            candidates[entity] = spark.table(staging)
        independent_staging = f"{AUDIT}._phase2d_stage_independent_{safe_run}"
        _independent_reconciliation_source(stock, facilities, points).write.format(
            "delta"
        ).mode("overwrite").saveAsTable(independent_staging)
        staging_tables.append(independent_staging)
        independent = spark.table(independent_staging)
        checked_at = _utcnow()
        regional_staging = f"{AUDIT}._phase2d_stage_reconciliation_{safe_run}"
        _regional_reconciliation(
            candidates, independent, run_id, identifier, checked_at
        ).write.format("delta").mode("overwrite").saveAsTable(regional_staging)
        staging_tables.append(regional_staging)
        regional = spark.table(regional_staging)
        sample_frame, sample_summary = _sample_recomputation(
            spark, candidates, independent, run_id, identifier, checked_at
        )
        sample_staging = f"{AUDIT}._phase2d_stage_samples_{safe_run}"
        sample_frame.write.format("delta").mode("overwrite").saveAsTable(sample_staging)
        staging_tables.append(sample_staging)
        sample_frame = spark.table(sample_staging)
        sample_failures = sample_frame.where("NOT all_checks_pass").count()
        _assertion(checks, "QA-001", "manual sample recomputation failures", 0, sample_failures, sample_failures)
        controls = _collect_controls_and_checks(
            spark, manifest, kpi_config, regions, stock, facilities, points,
            candidates, regional, checks,
        )
        fingerprints = _candidate_fingerprints(candidates)
        existing_gold_rows = sum(
            spark.table(table).where(f"date_set_id = {_sql_literal(identifier)}").count()
            if spark.catalog.tableExists(table)
            else 0
            for table in GOLD_TABLES.values()
        )
        action = "NO_OP" if registry_state == "published" else "PUBLISH"
        if action == "NO_OP" and existing_gold_rows != 1200:
            raise ValueError(
                f"Published registry state has incomplete Gold rows: {existing_gold_rows}/1200"
            )
        if action == "PUBLISH":
            _persist_candidates(candidates, run_id, started)
        _publish_checks(spark, run_id, identifier, checks, checked_at)
        regional.write.format("delta").mode("append").saveAsTable(
            f"{AUDIT}.gold_reconciliation_region"
        )
        sample_frame.write.format("delta").mode("append").saveAsTable(
            f"{AUDIT}.gold_sample_recomputation"
        )
        failures = [check for check in checks if check["result"] == "FAIL" and check["blocking"]]
        if failures:
            spark.sql(
                f"UPDATE {AUDIT}.date_set_registry SET state = 'failed' "
                f"WHERE date_set_id = {_sql_literal(identifier)} AND state <> 'published'"
            )
            raise ValueError(
                "Blocking Gold DQ failures: " + canonical_json({"failures": failures})
            )
        validated_at = _utcnow()
        if registry_state != "published":
            spark.sql(
                f"UPDATE {AUDIT}.date_set_registry SET state = 'validated' "
                f"WHERE date_set_id = {_sql_literal(identifier)} AND state = 'candidate'"
            )
        publication_action = _publish_gold_entities(
            spark, candidates, fingerprints, identifier, manifest, validated_at
        )
        if publication_action != action:
            raise ValueError(
                f"Registry-derived action {action} != entity publication action {publication_action}; "
                f"existing_gold_rows={existing_gold_rows}"
            )
        for entity, destination in GOLD_TABLES.items():
            published = spark.table(destination).where(
                f"date_set_id = {_sql_literal(identifier)}"
            )
            rows, fingerprint = _fingerprint(published, {"published_at"})
            _assertion(checks, f"POST-{entity}-001", f"{entity} published rows", 400, rows)
            _assertion(
                checks,
                f"POST-{entity}-002",
                f"{entity} published fingerprint",
                fingerprints[entity]["content_fingerprint"],
                fingerprint,
            )
        post_checks = checks[-6:]
        _publish_checks(spark, run_id, identifier, post_checks, _utcnow())
        post_failures = [check for check in post_checks if check["result"] == "FAIL"]
        if post_failures:
            raise ValueError(
                "Post-publication Gold checks failed: "
                + canonical_json({"failures": post_failures})
            )
        _create_serving_views(spark)
        if registry_state != "published":
            spark.sql(
                f"UPDATE {AUDIT}.date_set_registry SET state = 'published' "
                f"WHERE date_set_id = {_sql_literal(identifier)} AND state = 'validated'"
            )
        completed = _utcnow()
        passed = len([check for check in checks if check["result"] == "PASS"])
        _update_run(
            spark,
            run_id,
            {
                "candidate_created_at": started,
                "validated_at": validated_at,
                "published_at": validated_at if action == "PUBLISH" else None,
                "completed_at": completed,
                "status": "SUCCESS",
                "action": action,
                "candidate_fingerprints_json": canonical_json(fingerprints),
                "published_fingerprints_json": canonical_json(fingerprints),
                "passed_dq_checks": passed,
                "failed_dq_checks": 0,
            },
        )
        return {
            "result": "PASS",
            "action": action,
            "gold_run_id": run_id,
            "date_set_id": identifier,
            "controls": controls,
            "dq_checks": {"passed": passed, "failed": 0},
            "entities": fingerprints,
            "sample_recomputation": sample_summary,
            "serving_views": [
                f"{GOLD}.vw_powerbi_region_kpi_published",
                f"{GOLD}.vw_powerbi_date_set_quality",
            ],
        }
    except Exception as error:
        completed = _utcnow()
        try:
            if registry_state != "published":
                spark.sql(
                    f"UPDATE {AUDIT}.date_set_registry SET state = 'failed' "
                    f"WHERE date_set_id = {_sql_literal(identifier)} AND state <> 'published'"
                )
            _update_run(
                spark,
                run_id,
                {
                    "completed_at": completed,
                    "status": "FAILED",
                    "action": "BLOCKED",
                    "failure_reason": f"{type(error).__name__}: {error}"[:8000],
                },
            )
        finally:
            pass
        raise
    finally:
        for staging in staging_tables:
            spark.sql(f"DROP TABLE IF EXISTS {staging}")
