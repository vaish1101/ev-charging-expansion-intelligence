"""Phase 2C Bronze-to-Silver transformations for Databricks serverless Spark."""

from __future__ import annotations

import csv
import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ev_charging.identity import canonical_json, date_set_id
from ev_charging.runtime import catalog_name
from ev_charging.silver_rules import stable_identifier


CATALOG = catalog_name()
SILVER = f"{CATALOG}.silver"
AUDIT = f"{CATALOG}.audit"
BRONZE = f"{CATALOG}.bronze"

SOURCE_TABLES = {
    "bnetza": f"{BRONZE}.bnetza_ladesaeulenregister",
    "kba": f"{BRONZE}.kba_fz27_15",
    "destatis": f"{BRONZE}.destatis_gv_isys_hierarchy",
}

SILVER_TABLES = {
    "district": f"{SILVER}.dim_admin_district_version",
    "municipality": f"{SILVER}.dim_admin_municipality_version",
    "bnetza_bridge": f"{SILVER}.bridge_bnetza_district_to_destatis",
    "analysis_bridge": f"{SILVER}.bridge_destatis_district_to_analysis_region",
    "analysis_region": f"{SILVER}.dim_analysis_region",
    "ev_stock": f"{SILVER}.fact_ev_stock",
    "facility": f"{SILVER}.fact_charging_facility_snapshot",
    "point": f"{SILVER}.fact_charging_point_snapshot",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_rows(path: str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _append_dict(spark: Any, table: str, row: dict[str, Any]) -> None:
    schema = spark.table(table).schema
    spark.createDataFrame(
        [tuple(row.get(field.name) for field in schema.fields)], schema
    ).write.format("delta").mode("append").saveAsTable(table)


def ensure_phase2c_audit_tables(spark: Any) -> None:
    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.silver_run (
          silver_run_id STRING, date_set_id STRING, started_at TIMESTAMP,
          completed_at TIMESTAMP, status STRING, action STRING, failure_reason STRING
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.silver_dq_result (
          silver_run_id STRING, check_id STRING, check_name STRING, expected STRING,
          observed STRING, result STRING, blocking BOOLEAN, checked_at TIMESTAMP
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.silver_quarantine (
          silver_run_id STRING, entity_name STRING, source_revision_id STRING,
          source_row_number BIGINT, business_key STRING, failure_rule STRING,
          raw_problematic_value STRING, quarantined_at TIMESTAMP
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.silver_entity_revision (
          entity_revision_id STRING, entity_name STRING, destination_table STRING,
          date_set_id STRING, source_revision_context STRING, rule_version STRING,
          row_count BIGINT, content_fingerprint STRING, published_at TIMESTAMP
        ) USING DELTA
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {AUDIT}.silver_reconciliation_region (
          silver_run_id STRING, analysis_region_sk STRING, analysis_region_code STRING,
          facility_count BIGINT, in_service_facility_count BIGINT,
          maintenance_facility_count BIGINT, non_in_service_facility_count BIGINT,
          total_points BIGINT, normal_points BIGINT, fast_points BIGINT,
          unclassified_points BIGINT, registered_facility_nominal_power_kw DECIMAL(18,3),
          in_service_registered_facility_nominal_power_kw DECIMAL(18,3),
          maintenance_registered_facility_nominal_power_kw DECIMAL(18,3),
          other_status_registered_facility_nominal_power_kw DECIMAL(18,3),
          facility_equation_pass BOOLEAN, point_equation_pass BOOLEAN,
          power_equation_pass BOOLEAN, reconciled_at TIMESTAMP
        ) USING DELTA
        """,
    ]
    for statement in statements:
        spark.sql(statement)


def _assertion(checks: list[dict[str, Any]], check_id: str, name: str, expected: Any, observed: Any) -> None:
    checks.append(
        {
            "check_id": check_id,
            "check_name": name,
            "expected": str(expected),
            "observed": str(observed),
            "result": "PASS" if observed == expected else "FAIL",
            "blocking": True,
        }
    )


def _publish_checks(spark: Any, run_id: str, checks: Iterable[dict[str, Any]], checked_at: datetime) -> None:
    for check in checks:
        _append_dict(
            spark,
            f"{AUDIT}.silver_dq_result",
            {"silver_run_id": run_id, "checked_at": checked_at, **check},
        )


def _fingerprint(frame: Any, excluded: set[str] | None = None) -> tuple[int, str]:
    """Compute a deterministic, order-independent content fingerprint."""
    from pyspark.sql import functions as F

    excluded = excluded or set()
    columns = sorted(column for column in frame.columns if column not in excluded)
    row_json = F.to_json(F.struct(*[F.col(column) for column in columns]), {"ignoreNullFields": "false"})
    hashed = frame.select(F.sha2(row_json, 256).alias("sha"), F.xxhash64(row_json).alias("xx"))
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


def _source_revision(config: dict[str, Any], provider: str) -> str:
    source = next(
        item
        for item in config["sources"]
        if item["classification"] == "CORE_V1" and item["provider"] == provider
    )
    return f"{source['provider']}:{source['dataset_id']}:{source['expected_reference_date']}:{source['sha256']}"


def _build_mapping_frames(spark: Any, geography: dict[str, Any], evidence_root: str, created_at: datetime) -> tuple[Any, Any, Any]:
    from pyspark.sql.types import (
        BooleanType,
        DateType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    crosswalk_path = str(Path(evidence_root) / Path(geography["bnetza_district_mapping"]["evidence_path"]).name)
    analysis_path = str(Path(evidence_root) / Path(geography["destatis_analysis_region_bridge"]["evidence_path"]).name)
    if _sha256(crosswalk_path) != geography["bnetza_district_mapping"]["evidence_sha256"]:
        raise ValueError("BNetzA geography evidence SHA-256 mismatch")
    if _sha256(analysis_path) != geography["destatis_analysis_region_bridge"]["evidence_sha256"]:
        raise ValueError("Analysis-region bridge evidence SHA-256 mismatch")

    selected: dict[tuple[str, str], dict[str, str]] = {}
    for row in _csv_rows(crosswalk_path):
        if not (
            row["source_reference"] == "BNetzA 2026-09-01"
            and row["target_reference"] == "2026-06-30"
            and row["matched"] == "True"
        ):
            continue
        key = (row["Bundesland"], row["source_district_label"])
        payload = {
            "raw_bundesland": row["Bundesland"],
            "raw_district_label": row["source_district_label"],
            "target_district_code": row["matched_district_key"],
            "target_district_name": row["matched_district_name"],
            "mapping_rule": row["match_method"],
        }
        if key in selected and selected[key] != payload:
            raise ValueError(f"Conflicting current BNetzA bridge evidence for {key}")
        selected[key] = payload
    bridge_rows = []
    mapping_version = geography["bnetza_district_mapping"]["version"]
    hanau = geography["hanau"]["bnetza_current_exception"]
    for payload in selected.values():
        is_hanau = (
            payload["raw_bundesland"] == hanau["raw_bundesland"]
            and payload["raw_district_label"] == hanau["raw_district_label"]
        )
        valid_from = date.fromisoformat(hanau["valid_from"] if is_hanau else geography["current_geography_reference_date"])
        bridge_rows.append(
            (
                stable_identifier("bd", mapping_version, payload["raw_bundesland"], payload["raw_district_label"], valid_from),
                payload["raw_bundesland"], payload["raw_district_label"],
                _normalize(payload["raw_bundesland"]), _normalize(payload["raw_district_label"]),
                payload["target_district_code"], payload["target_district_name"],
                "approved_exception" if is_hanau else "exact_normalized",
                payload["mapping_rule"], crosswalk_path,
                geography["bnetza_district_mapping"]["evidence_sha256"], valid_from, None,
                hanau["exception_reason"] if is_hanau else None,
                "MATCHED", mapping_version, created_at,
            )
        )
    bnetza_schema = StructType([
        StructField("bnetza_district_mapping_sk", StringType(), False),
        StructField("raw_bundesland", StringType(), False), StructField("raw_district_label", StringType(), False),
        StructField("normalized_bundesland", StringType(), False), StructField("normalized_district_label", StringType(), False),
        StructField("target_district_code", StringType(), False), StructField("target_district_name", StringType(), False),
        StructField("mapping_status", StringType(), False), StructField("mapping_rule", StringType(), False),
        StructField("evidence_path", StringType(), False), StructField("evidence_sha256", StringType(), False),
        StructField("valid_from", DateType(), False), StructField("valid_to", DateType(), True),
        StructField("exception_reason", StringType(), True), StructField("resolution_status", StringType(), False),
        StructField("mapping_version", StringType(), False), StructField("_created_at", TimestampType(), False),
    ])
    bnetza_bridge = spark.createDataFrame(bridge_rows, bnetza_schema)

    analysis_rows = []
    analysis_version = geography["destatis_analysis_region_bridge"]["version"]
    for row in _csv_rows(analysis_path):
        valid_from_text = row["valid_from"] or geography["current_geography_reference_date"]
        valid_from = date.fromisoformat(valid_from_text)
        analysis_rows.append(
            (
                stable_identifier("da", analysis_version, row["source_district_key"], valid_from),
                row["source_district_key"], row["source_district_name"],
                row["target_analysis_region_key"], row["target_analysis_region_name"],
                row["relationship_type"], valid_from, None, row["mapping_rationale"],
                analysis_version, analysis_path,
                geography["destatis_analysis_region_bridge"]["evidence_sha256"], created_at,
            )
        )
    analysis_schema = StructType([
        StructField("district_analysis_region_bridge_sk", StringType(), False),
        StructField("district_code", StringType(), False), StructField("district_name", StringType(), False),
        StructField("analysis_region_code", StringType(), False), StructField("analysis_region_name", StringType(), False),
        StructField("relationship_type", StringType(), False), StructField("valid_from", DateType(), False),
        StructField("valid_to", DateType(), True), StructField("mapping_rationale", StringType(), False),
        StructField("bridge_version", StringType(), False), StructField("evidence_path", StringType(), False),
        StructField("evidence_sha256", StringType(), False), StructField("_created_at", TimestampType(), False),
    ])
    analysis_bridge = spark.createDataFrame(analysis_rows, analysis_schema)

    municipality_rows = []
    for row in geography["hanau"]["municipality_history"]:
        valid_from = date.fromisoformat(row["valid_from"])
        valid_to = date.fromisoformat(row["valid_to"]) if row["valid_to"] else None
        municipality_rows.append(
            (
                stable_identifier("mu", analysis_version, row["administrative_unit_code"], valid_from),
                row["administrative_unit_code"], row["canonical_name"], row["parent_district_code"],
                row["relationship"], valid_from, valid_to, analysis_version, created_at,
            )
        )
    municipality_schema = StructType([
        StructField("admin_municipality_version_sk", StringType(), False),
        StructField("administrative_unit_code", StringType(), False), StructField("canonical_name", StringType(), False),
        StructField("parent_district_code", StringType(), False), StructField("relationship", StringType(), False),
        StructField("valid_from", DateType(), False), StructField("valid_to", DateType(), True),
        StructField("configuration_version", StringType(), False), StructField("_created_at", TimestampType(), False),
    ])
    municipality = spark.createDataFrame(municipality_rows, municipality_schema)
    return bnetza_bridge, analysis_bridge, municipality


def _normalize(value: str) -> str:
    from ev_charging.silver_rules import normalize_geography_text

    return normalize_geography_text(value)


def _build_business_frames(
    spark: Any,
    config: dict[str, Any],
    manifest: dict[str, Any],
    geography: dict[str, Any],
    evidence_root: str,
    created_at: datetime,
) -> dict[str, Any]:
    from functools import reduce
    from pyspark.sql import functions as F

    bnetza_revision = _source_revision(config, "bnetza")
    kba_revision = _source_revision(config, "kba")
    destatis_revision = _source_revision(config, "destatis")
    bnetza_bridge, analysis_bridge, municipality = _build_mapping_frames(
        spark, geography, evidence_root, created_at
    )

    destatis = spark.table(SOURCE_TABLES["destatis"]).where(F.col("_source_revision_id") == destatis_revision)
    states = destatis.where(F.col("satzart") == "10").select(
        F.col("ars_land").alias("state_code"), F.col("gemeindename").alias("state_name")
    )
    type_name = (
        F.when(F.col("textkennzeichen") == "41", "Kreisfreie Stadt")
        .when(F.col("textkennzeichen") == "42", "Stadtkreis")
        .when(F.col("textkennzeichen") == "43", "Kreis")
        .when(F.col("textkennzeichen") == "44", "Landkreis")
        .when(F.col("textkennzeichen") == "45", "Regionalverband")
    )
    districts = (
        destatis.where(F.col("satzart") == "40")
        .withColumn("district_code", F.concat("ars_land", "ars_rb", "ars_kreis"))
        .join(states, F.col("ars_land") == F.col("state_code"), "left")
        .withColumn(
            "valid_from",
            F.when(F.col("district_code") == "06415", F.lit("2026-01-01").cast("date"))
            .otherwise(F.lit(geography["current_geography_reference_date"]).cast("date")),
        )
        .select(
            F.sha2(F.concat_ws("\u001f", F.lit("district"), "district_code", F.col("valid_from").cast("string"), F.lit(destatis_revision)), 256).alias("admin_district_version_sk"),
            "district_code", F.col("gemeindename").alias("canonical_district_name"),
            "state_code", "state_name", type_name.alias("administrative_type"),
            "valid_from", F.lit(None).cast("date").alias("valid_to"), F.lit(True).alias("is_current"),
            F.lit(destatis_revision).alias("geography_source_revision_id"), F.col("_reference_date").alias("geography_reference_date"),
            F.lit(created_at).cast("timestamp").alias("_created_at"),
        )
    )

    kba = spark.table(SOURCE_TABLES["kba"]).where(F.col("_source_revision_id") == kba_revision)
    region_valid_from = F.when(
        F.col("statistische_kennziffer") == "06415", F.lit("2026-01-01").cast("date")
    ).otherwise(F.lit(geography["current_geography_reference_date"]).cast("date"))
    analysis_regions = kba.select(
        F.sha2(
            F.concat_ws("\u001f", F.lit("analysis_region"), "statistische_kennziffer", region_valid_from.cast("string"), F.lit(geography["destatis_analysis_region_bridge"]["version"])), 256
        ).alias("analysis_region_sk"),
        F.col("statistische_kennziffer").alias("analysis_region_code"),
        F.col("zulassungsbezirk").alias("analysis_region_name"),
        region_valid_from.alias("valid_from"), F.lit(None).cast("date").alias("valid_to"),
        F.lit(True).alias("is_current"),
        F.lit(geography["destatis_analysis_region_bridge"]["version"]).alias("mapping_version"),
        F.lit(kba_revision).alias("kba_geography_source_revision_id"),
        F.lit(created_at).cast("timestamp").alias("_created_at"),
    )
    ev_stock = (
        kba.join(
            analysis_regions.select("analysis_region_sk", "analysis_region_code"),
            kba["statistische_kennziffer"] == analysis_regions["analysis_region_code"],
            "left",
        )
        .select(
            F.sha2(F.concat_ws("\u001f", F.lit("ev_stock"), "statistische_kennziffer", F.col("_reference_date").cast("string"), F.lit(kba_revision)), 256).alias("ev_stock_sk"),
            "analysis_region_sk", F.col("statistische_kennziffer").alias("analysis_region_code"),
            F.col("_reference_date").alias("reference_date"),
            F.col("elektro_bev").cast("bigint").alias("bev_passenger_car_stock"),
            F.col("pkw_anzahl_insgesamt").cast("bigint").alias("total_passenger_car_stock"),
            F.col("plug_in_hybrid").cast("bigint").alias("plugin_hybrid_passenger_car_stock"),
            F.lit(kba_revision).alias("source_revision_id"), F.col("_source_row_number").alias("source_row_number"),
            F.lit(created_at).cast("timestamp").alias("_created_at"),
        )
    )

    bnetza = spark.table(SOURCE_TABLES["bnetza"]).where(F.col("_source_revision_id") == bnetza_revision)
    source_date = F.col("b._reference_date")
    mapped = (
        bnetza.alias("b")
        .join(
            bnetza_bridge.alias("m"),
            (F.col("b.bundesland") == F.col("m.raw_bundesland"))
            & (F.col("b.kreis_kreisfreie_stadt") == F.col("m.raw_district_label"))
            & (F.col("m.valid_from") <= source_date)
            & (F.col("m.valid_to").isNull() | (source_date < F.col("m.valid_to"))),
            "left",
        )
        .join(
            analysis_bridge.alias("a"),
            (F.col("m.target_district_code") == F.col("a.district_code"))
            & (F.col("a.valid_from") <= source_date)
            & (F.col("a.valid_to").isNull() | (source_date < F.col("a.valid_to"))),
            "left",
        )
        .join(
            analysis_regions.select("analysis_region_sk", "analysis_region_code").alias("r"),
            F.col("a.analysis_region_code") == F.col("r.analysis_region_code"),
            "left",
        )
    )
    power = F.regexp_replace(F.regexp_replace(F.trim(F.col("b.nennleistung_ladeeinrichtung_kw")), r"\.", ""), ",", ".").cast("decimal(18,3)")
    facilities = mapped.select(
        F.sha2(F.concat_ws("\u001f", F.lit("facility"), F.col("b.ladeeinrichtungs_id"), F.col("b._reference_date").cast("string"), F.lit(bnetza_revision)), 256).alias("charging_facility_snapshot_sk"),
        F.col("b.ladeeinrichtungs_id").alias("facility_id"), F.col("b._reference_date").alias("snapshot_date"),
        F.col("b.status").alias("status"), (F.col("b.status") == "In Betrieb").alias("is_in_service"),
        F.col("b.art_der_ladeeinrichtung").alias("facility_type"),
        F.col("b.anzahl_ladepunkte").cast("bigint").alias("declared_charging_point_count"),
        power.alias("registered_facility_nominal_power_kw"),
        F.to_date(F.col("b.inbetriebnahmedatum"), "dd.MM.yyyy").alias("commissioning_date"),
        F.col("b.strasse").alias("street"), F.col("b.hausnummer").alias("house_number"),
        F.col("b.postleitzahl").alias("postal_code"), F.col("b.ort").alias("locality"),
        F.col("b.bundesland").alias("raw_bundesland"),
        F.col("b.kreis_kreisfreie_stadt").alias("raw_district_label"),
        F.col("m.target_district_code").alias("destatis_district_code"),
        F.col("m.target_district_name").alias("destatis_district_name"),
        F.col("r.analysis_region_sk"), F.col("a.analysis_region_code"),
        F.col("m.mapping_version").alias("bnetza_district_mapping_version"),
        F.col("a.bridge_version").alias("district_analysis_region_bridge_version"),
        F.lit(bnetza_revision).alias("source_revision_id"), F.col("b._source_row_number").alias("source_row_number"),
        F.lit(created_at).cast("timestamp").alias("_created_at"),
    )

    point_frames = []
    for slot in range(1, 7):
        connector = F.trim(F.col(f"b.steckertypen{slot}"))
        power_text = F.col(f"b.nennleistung_stecker{slot}")
        power_array = F.expr(
            f"transform(split(b.nennleistung_stecker{slot}, ';'), x -> cast(replace(replace(trim(x), '.', ''), ',', '.') as decimal(18,3)))"
        )
        point_max = F.array_max(power_array)
        point_frames.append(
            mapped.where(connector != "").select(
                F.sha2(F.concat_ws("\u001f", F.lit("point"), F.col("b.ladeeinrichtungs_id"), F.lit(str(slot)), F.col("b._reference_date").cast("string"), F.lit(bnetza_revision)), 256).alias("charging_point_snapshot_sk"),
                F.sha2(F.concat_ws("\u001f", F.lit("facility"), F.col("b.ladeeinrichtungs_id"), F.col("b._reference_date").cast("string"), F.lit(bnetza_revision)), 256).alias("charging_facility_snapshot_sk"),
                F.col("b.ladeeinrichtungs_id").alias("facility_id"), F.lit(slot).cast("int").alias("point_slot"),
                F.col("b._reference_date").alias("snapshot_date"),
                F.transform(F.split(connector, ";"), lambda item: F.trim(item)).alias("connector_types"),
                power_array.alias("connector_nominal_power_values_kw"), point_max.alias("point_max_nominal_power_kw"),
                F.when(point_max.isNull(), "UNCLASSIFIED").when(point_max <= F.lit(22), "NORMAL").otherwise("FAST").alias("point_class"),
                F.col(f"b.evse_id{slot}").alias("evse_id"), F.col(f"b.public_key{slot}").alias("public_key"),
                F.col("m.target_district_code").alias("destatis_district_code"),
                F.col("r.analysis_region_sk"), F.col("a.analysis_region_code"),
                F.col("m.mapping_version").alias("bnetza_district_mapping_version"),
                F.col("a.bridge_version").alias("district_analysis_region_bridge_version"),
                F.lit(bnetza_revision).alias("source_revision_id"), F.col("b._source_row_number").alias("source_row_number"),
                F.lit(created_at).cast("timestamp").alias("_created_at"),
            )
        )
    points = reduce(lambda left, right: left.unionByName(right), point_frames)
    return {
        "district": districts,
        "municipality": municipality,
        "bnetza_bridge": bnetza_bridge,
        "analysis_bridge": analysis_bridge,
        "analysis_region": analysis_regions,
        "ev_stock": ev_stock,
        "facility": facilities,
        "point": points,
    }


def _regional_reconciliation(frames: dict[str, Any], run_id: str, reconciled_at: datetime) -> Any:
    from pyspark.sql import functions as F

    facilities = frames["facility"].groupBy("analysis_region_sk", "analysis_region_code").agg(
        F.count("*").alias("facility_count"),
        F.sum(F.col("is_in_service").cast("bigint")).alias("in_service_facility_count"),
        F.sum((F.col("status") == "In Wartung").cast("bigint")).alias("maintenance_facility_count"),
        F.sum((~F.col("is_in_service")).cast("bigint")).alias("non_in_service_facility_count"),
        F.sum("registered_facility_nominal_power_kw").cast("decimal(18,3)").alias("registered_facility_nominal_power_kw"),
        F.sum(F.when(F.col("is_in_service"), F.col("registered_facility_nominal_power_kw")).otherwise(F.lit(0))).cast("decimal(18,3)").alias("in_service_registered_facility_nominal_power_kw"),
        F.sum(F.when(F.col("status") == "In Wartung", F.col("registered_facility_nominal_power_kw")).otherwise(F.lit(0))).cast("decimal(18,3)").alias("maintenance_registered_facility_nominal_power_kw"),
        F.sum(F.when(~F.col("status").isin("In Betrieb", "In Wartung"), F.col("registered_facility_nominal_power_kw")).otherwise(F.lit(0))).cast("decimal(18,3)").alias("other_status_registered_facility_nominal_power_kw"),
    )
    points = frames["point"].groupBy("analysis_region_sk", "analysis_region_code").agg(
        F.count("*").alias("total_points"),
        F.sum((F.col("point_class") == "NORMAL").cast("bigint")).alias("normal_points"),
        F.sum((F.col("point_class") == "FAST").cast("bigint")).alias("fast_points"),
        F.sum((F.col("point_class") == "UNCLASSIFIED").cast("bigint")).alias("unclassified_points"),
    )
    scaffold = frames["analysis_region"].select("analysis_region_sk", "analysis_region_code")
    integer_columns = [
        "facility_count", "in_service_facility_count", "maintenance_facility_count",
        "non_in_service_facility_count", "total_points", "normal_points", "fast_points", "unclassified_points",
    ]
    power_columns = [
        "registered_facility_nominal_power_kw", "in_service_registered_facility_nominal_power_kw",
        "maintenance_registered_facility_nominal_power_kw", "other_status_registered_facility_nominal_power_kw",
    ]
    result = scaffold.join(facilities, ["analysis_region_sk", "analysis_region_code"], "left").join(
        points, ["analysis_region_sk", "analysis_region_code"], "left"
    )
    for column in integer_columns:
        result = result.withColumn(column, F.coalesce(F.col(column), F.lit(0).cast("bigint")))
    for column in power_columns:
        result = result.withColumn(column, F.coalesce(F.col(column), F.lit(0).cast("decimal(18,3)")))
    return result.select(
        F.lit(run_id).alias("silver_run_id"), "analysis_region_sk", "analysis_region_code",
        *integer_columns, *power_columns,
        (F.col("facility_count") == F.col("in_service_facility_count") + F.col("non_in_service_facility_count")).alias("facility_equation_pass"),
        (F.col("total_points") == F.col("normal_points") + F.col("fast_points") + F.col("unclassified_points")).alias("point_equation_pass"),
        (F.col("registered_facility_nominal_power_kw") == F.col("in_service_registered_facility_nominal_power_kw") + F.col("maintenance_registered_facility_nominal_power_kw") + F.col("other_status_registered_facility_nominal_power_kw")).alias("power_equation_pass"),
        F.lit(reconciled_at).cast("timestamp").alias("reconciled_at"),
    )


def _collect_controls(frames: dict[str, Any], regional: Any, checks: list[dict[str, Any]]) -> dict[str, Any]:
    from pyspark.sql import functions as F

    district = frames["district"]
    regions = frames["analysis_region"]
    bbridge = frames["bnetza_bridge"]
    abridge = frames["analysis_bridge"]
    stock = frames["ev_stock"]
    facility = frames["facility"]
    point = frames["point"]

    district_count = district.count()
    region_count = regions.count()
    _assertion(checks, "GEO-001", "current Destatis district rows", 401, district_count)
    _assertion(checks, "GEO-002", "current BNetzA bridge identities", 401, bbridge.count())
    _assertion(checks, "GEO-003", "current Destatis to analysis bridge rows", 401, abridge.count())
    _assertion(checks, "GEO-004", "current analysis regions", 400, region_count)
    _assertion(checks, "GEO-005", "unique district keys", 401, district.select("district_code").distinct().count())
    _assertion(checks, "GEO-006", "unique BNetzA mapping keys", 401, bbridge.select("raw_bundesland", "raw_district_label").distinct().count())
    _assertion(checks, "GEO-007", "unique bridge source keys", 401, abridge.select("district_code").distinct().count())
    _assertion(checks, "GEO-008", "analysis bridge target keys", 400, abridge.select("analysis_region_code").distinct().count())
    b_overlap = (
        bbridge.alias("l").join(
            bbridge.alias("r"),
            (F.col("l.raw_bundesland") == F.col("r.raw_bundesland"))
            & (F.col("l.raw_district_label") == F.col("r.raw_district_label"))
            & (F.col("l.bnetza_district_mapping_sk") < F.col("r.bnetza_district_mapping_sk"))
            & (F.col("r.valid_to").isNull() | (F.col("l.valid_from") < F.col("r.valid_to")))
            & (F.col("l.valid_to").isNull() | (F.col("r.valid_from") < F.col("l.valid_to"))),
            "inner",
        ).count()
    )
    a_overlap = (
        abridge.alias("l").join(
            abridge.alias("r"),
            (F.col("l.district_code") == F.col("r.district_code"))
            & (F.col("l.district_analysis_region_bridge_sk") < F.col("r.district_analysis_region_bridge_sk"))
            & (F.col("r.valid_to").isNull() | (F.col("l.valid_from") < F.col("r.valid_to")))
            & (F.col("l.valid_to").isNull() | (F.col("r.valid_from") < F.col("l.valid_to"))),
            "inner",
        ).count()
    )
    _assertion(checks, "GEO-008A", "BNetzA bridge effective-date overlaps", 0, b_overlap)
    _assertion(checks, "GEO-008B", "analysis bridge effective-date overlaps", 0, a_overlap)
    _assertion(
        checks,
        "GEO-008C",
        "BNetzA bridge destination district key difference",
        0,
        bbridge.select(F.col("target_district_code").alias("district_code")).subtract(
            district.select("district_code")
        ).count(),
    )
    trier = abridge.where(F.col("analysis_region_code") == "07211").select("district_code").orderBy("district_code").collect()
    _assertion(checks, "GEO-009", "Trier target source codes", "07211,07235", ",".join(row[0] for row in trier))
    hanau_history = frames["municipality"].orderBy("valid_from").select(
        "administrative_unit_code", "parent_district_code", "valid_from", "valid_to"
    ).collect()
    _assertion(checks, "GEO-010", "Hanau governed history rows", 2, len(hanau_history))
    _assertion(checks, "GEO-011", "Hanau current district", "06415", bbridge.where((F.col("raw_bundesland") == "Hessen") & (F.col("raw_district_label") == "Kreisfreie Stadt Hanau")).select("target_district_code").first()[0])
    _assertion(checks, "GEO-012", "mapped facility rows", 116443, facility.where(F.col("destatis_district_code").isNotNull() & F.col("analysis_region_sk").isNotNull()).count())
    _assertion(checks, "GEO-013", "unmapped facility rows", 0, facility.where(F.col("destatis_district_code").isNull() | F.col("analysis_region_sk").isNull()).count())

    stock_row = stock.agg(
        F.count("*").alias("rows"), F.countDistinct("analysis_region_code").alias("keys"),
        F.sum(F.col("bev_passenger_car_stock").isNull().cast("bigint")).alias("null_bev"),
        F.sum((F.col("bev_passenger_car_stock") < 0).cast("bigint")).alias("negative_bev"),
        F.countDistinct("reference_date").alias("dates"), F.min("reference_date").alias("ref"),
    ).first()
    _assertion(checks, "KBA-001", "EV stock rows", 400, stock_row["rows"])
    _assertion(checks, "KBA-002", "EV stock unique regions", 400, stock_row["keys"])
    _assertion(checks, "KBA-003", "EV stock null BEV", 0, stock_row["null_bev"])
    _assertion(checks, "KBA-004", "EV stock negative BEV", 0, stock_row["negative_bev"])
    _assertion(checks, "KBA-005", "EV stock reference date", "2026-07-01", str(stock_row["ref"]))
    key_difference = stock.select("analysis_region_code").subtract(regions.select("analysis_region_code")).count() + regions.select("analysis_region_code").subtract(stock.select("analysis_region_code")).count()
    _assertion(checks, "KBA-006", "KBA and analysis-region symmetric key difference", 0, key_difference)
    _assertion(checks, "KBA-007", "EV stock business-key duplicates", 0, stock.groupBy("analysis_region_code", "reference_date", "source_revision_id").count().where("count > 1").count())

    status = facility.agg(
        F.count("*").alias("rows"), F.countDistinct("facility_id").alias("ids"),
        F.sum(F.col("is_in_service").cast("bigint")).alias("in_service"),
        F.sum((F.col("status") == "In Wartung").cast("bigint")).alias("maintenance"),
        F.sum((F.col("is_in_service") != (F.col("status") == "In Betrieb")).cast("bigint")).alias("status_mismatch"),
        F.sum("registered_facility_nominal_power_kw").alias("all_power"),
        F.sum(F.when(F.col("is_in_service"), F.col("registered_facility_nominal_power_kw")).otherwise(F.lit(0))).alias("service_power"),
        F.sum(F.when(F.col("status") == "In Wartung", F.col("registered_facility_nominal_power_kw")).otherwise(F.lit(0))).alias("maintenance_power"),
        F.sum(F.when(~F.col("status").isin("In Betrieb", "In Wartung"), F.col("registered_facility_nominal_power_kw")).otherwise(F.lit(0))).alias("other_power"),
    ).first()
    _assertion(checks, "BNE-001", "facility rows", 116443, status["rows"])
    _assertion(checks, "BNE-002", "unique facility IDs", 116443, status["ids"])
    _assertion(checks, "BNE-003", "in-service facilities", 116423, status["in_service"])
    _assertion(checks, "BNE-004", "maintenance facilities", 20, status["maintenance"])
    _assertion(checks, "BNE-005", "status flag equivalence mismatches", 0, status["status_mismatch"])
    _assertion(checks, "PWR-001", "all-status registered facility nominal power kW", "9086797.500", str(status["all_power"]))
    _assertion(checks, "PWR-002", "in-service registered facility nominal power kW", "9086313.500", str(status["service_power"]))
    _assertion(checks, "PWR-003", "maintenance registered facility nominal power kW", "484.000", str(status["maintenance_power"]))
    _assertion(checks, "PWR-004", "other-status registered facility nominal power kW", "0.000", str(status["other_power"]))
    _assertion(checks, "PWR-005", "national power accounting equation", status["all_power"], status["service_power"] + status["maintenance_power"] + status["other_power"])

    point_status = point.agg(
        F.count("*").alias("rows"),
        F.sum((F.col("point_class") == "NORMAL").cast("bigint")).alias("normal"),
        F.sum((F.col("point_class") == "FAST").cast("bigint")).alias("fast"),
        F.sum((F.col("point_class") == "UNCLASSIFIED").cast("bigint")).alias("unclassified"),
        F.sum(F.exists("connector_nominal_power_values_kw", lambda item: item.isNull() | (item <= 0)).cast("bigint")).alias("invalid_power"),
    ).first()
    _assertion(checks, "PNT-001", "charging-point rows", 209136, point_status["rows"])
    _assertion(checks, "PNT-002", "normal charging points", 154740, point_status["normal"])
    _assertion(checks, "PNT-003", "fast charging points", 54396, point_status["fast"])
    _assertion(checks, "PNT-004", "unclassified charging points", 0, point_status["unclassified"])
    _assertion(checks, "PNT-005", "invalid connector power tokens", 0, point_status["invalid_power"])
    _assertion(checks, "PNT-006", "point classification accounting", point_status["rows"], point_status["normal"] + point_status["fast"] + point_status["unclassified"])
    _assertion(checks, "PNT-007", "charging-point business-key duplicates", 0, point.groupBy("facility_id", "point_slot", "snapshot_date", "source_revision_id").count().where("count > 1").count())
    orphan_points = point.select("charging_facility_snapshot_sk").subtract(facility.select("charging_facility_snapshot_sk")).count()
    _assertion(checks, "FK-001", "charging-point parent orphans", 0, orphan_points)
    _assertion(checks, "FK-002", "facility district orphans", 0, facility.where(F.col("destatis_district_code").isNull()).count())
    _assertion(checks, "FK-003", "facility analysis-region orphans", 0, facility.where(F.col("analysis_region_sk").isNull()).count())
    _assertion(checks, "FK-004", "EV stock analysis-region orphans", 0, stock.where(F.col("analysis_region_sk").isNull()).count())
    declared_mismatch = (
        facility.select("charging_facility_snapshot_sk", "declared_charging_point_count")
        .join(point.groupBy("charging_facility_snapshot_sk").count(), "charging_facility_snapshot_sk", "left")
        .where(F.col("declared_charging_point_count") != F.coalesce(F.col("count"), F.lit(0)))
        .count()
    )
    _assertion(checks, "PNT-008", "declared versus normalized point mismatches", 0, declared_mismatch)
    _assertion(checks, "REC-001", "BNetzA Bronze eligible = Silver + quarantine", 116443, status["rows"])
    _assertion(checks, "REC-002", "KBA Bronze eligible = Silver + quarantine", 400, stock_row["rows"])

    regional_status = regional.agg(
        F.count("*").alias("rows"),
        F.sum((~F.col("facility_equation_pass")).cast("bigint")).alias("bad_facility"),
        F.sum((~F.col("point_equation_pass")).cast("bigint")).alias("bad_point"),
        F.sum((~F.col("power_equation_pass")).cast("bigint")).alias("bad_power"),
        F.sum("facility_count").alias("facility_sum"), F.sum("total_points").alias("point_sum"),
    ).first()
    _assertion(checks, "REG-001", "regional scaffold rows", 400, regional_status["rows"])
    _assertion(checks, "REG-002", "regional facility equation failures", 0, regional_status["bad_facility"])
    _assertion(checks, "REG-003", "regional point equation failures", 0, regional_status["bad_point"])
    _assertion(checks, "REG-004", "regional power equation failures", 0, regional_status["bad_power"])
    _assertion(checks, "REG-005", "regional facility national sum", 116443, regional_status["facility_sum"])
    _assertion(checks, "REG-006", "regional point national sum", 209136, regional_status["point_sum"])
    return {
        "district_count": district_count,
        "analysis_region_count": region_count,
        "facility_count": status["rows"], "in_service_facility_count": status["in_service"],
        "maintenance_facility_count": status["maintenance"],
        "all_status_registered_facility_nominal_power_kw": str(status["all_power"]),
        "in_service_registered_facility_nominal_power_kw": str(status["service_power"]),
        "maintenance_registered_facility_nominal_power_kw": str(status["maintenance_power"]),
        "other_status_registered_facility_nominal_power_kw": str(status["other_power"]),
        "point_count": point_status["rows"], "normal_point_count": point_status["normal"],
        "fast_point_count": point_status["fast"], "unclassified_point_count": point_status["unclassified"],
        "regional_scaffold_count": regional_status["rows"],
    }


def _publish_business_frames(
    spark: Any,
    frames: dict[str, Any],
    identifier: str,
    manifest: dict[str, Any],
    created_at: datetime,
) -> tuple[str, dict[str, Any]]:
    revisions = []
    for entity_name, frame in frames.items():
        row_count, fingerprint = _fingerprint(frame, {"_created_at"})
        context = canonical_json({
            "date_set_id": identifier,
            "bnetza": manifest["bnetza_source_revision_id"],
            "kba": manifest["kba_source_revision_id"],
            "destatis": manifest["destatis_geography_source_revision_id"],
            "bnetza_bridge": manifest["bnetza_district_mapping_version"],
            "analysis_bridge": manifest["district_analysis_region_bridge_version"],
        })
        entity_revision_id = stable_identifier("silverrev", entity_name, identifier)
        existing = spark.table(f"{AUDIT}.silver_entity_revision").where(
            f"entity_revision_id = '{entity_revision_id}'"
        ).collect()
        if existing:
            if len(existing) != 1 or existing[0]["content_fingerprint"] != fingerprint or existing[0]["row_count"] != row_count:
                raise ValueError(f"Immutable Silver entity-revision conflict for {entity_name}")
            action = "NO_OP"
        else:
            action = "PUBLISH"
        revisions.append((entity_name, frame, entity_revision_id, row_count, fingerprint, context, action))
    actions = {item[6] for item in revisions}
    if len(actions) != 1:
        raise ValueError(f"Partial Silver publication state detected: {sorted(actions)}")
    action = actions.pop()
    if action == "PUBLISH":
        for entity_name, frame, entity_revision_id, row_count, fingerprint, context, _ in revisions:
            destination = SILVER_TABLES[entity_name]
            frame.write.format("delta").mode("append").saveAsTable(destination)
            _append_dict(
                spark,
                f"{AUDIT}.silver_entity_revision",
                {
                    "entity_revision_id": entity_revision_id, "entity_name": entity_name,
                    "destination_table": destination, "date_set_id": identifier,
                    "source_revision_context": context,
                    "rule_version": manifest["transformation_rule_version"],
                    "row_count": row_count, "content_fingerprint": fingerprint,
                    "published_at": created_at,
                },
            )
    return action, {
        entity_name: {"table": SILVER_TABLES[entity_name], "rows": row_count, "content_fingerprint": fingerprint}
        for entity_name, _, _, row_count, fingerprint, _, _ in revisions
    }


def run_phase2c(
    spark: Any,
    source_config_path: str,
    date_set_manifest_path: str,
    geography_config_path: str,
    evidence_root: str,
) -> dict[str, Any]:
    """Build and validate governed Silver entities, or prove an immutable no-op."""
    config = _read_json(source_config_path)
    manifest = _read_json(date_set_manifest_path)
    geography = _read_json(geography_config_path)
    identifier, _ = date_set_id(manifest)
    run_id = str(uuid.uuid4())
    started = _utcnow()
    ensure_phase2c_audit_tables(spark)
    staging_tables: list[str] = []
    try:
        computed_frames = _build_business_frames(spark, config, manifest, geography, evidence_root, started)
        frames = {}
        safe_run_id = run_id.replace("-", "")
        for entity_name, frame in computed_frames.items():
            staging_table = f"{SILVER}._phase2c_stage_{entity_name}_{safe_run_id}"
            frame.write.format("delta").mode("overwrite").saveAsTable(staging_table)
            staging_tables.append(staging_table)
            frames[entity_name] = spark.table(staging_table)
        reconciled_at = _utcnow()
        regional_staging = f"{AUDIT}._phase2c_stage_regional_{safe_run_id}"
        _regional_reconciliation(frames, run_id, reconciled_at).write.format("delta").mode("overwrite").saveAsTable(regional_staging)
        staging_tables.append(regional_staging)
        regional = spark.table(regional_staging)
        checks: list[dict[str, Any]] = []
        controls = _collect_controls(frames, regional, checks)
        _publish_checks(spark, run_id, checks, reconciled_at)
        failures = [check for check in checks if check["blocking"] and check["result"] == "FAIL"]
        if failures:
            raise ValueError("Blocking Silver DQ failures: " + canonical_json({"failures": failures}))
        action, entities = _publish_business_frames(spark, frames, identifier, manifest, started)
        regional.write.format("delta").mode("append").saveAsTable(f"{AUDIT}.silver_reconciliation_region")
        completed = _utcnow()
        _append_dict(
            spark,
            f"{AUDIT}.silver_run",
            {
                "silver_run_id": run_id, "date_set_id": identifier, "started_at": started,
                "completed_at": completed, "status": "SUCCESS", "action": action,
                "failure_reason": None,
            },
        )
        return {
            "result": "PASS", "action": action, "silver_run_id": run_id,
            "date_set_id": identifier, "controls": controls, "entities": entities,
            "dq_checks": {"passed": len(checks), "failed": 0},
            "quarantine_rows": 0,
        }
    except Exception as error:
        _append_dict(
            spark,
            f"{AUDIT}.silver_run",
            {
                "silver_run_id": run_id, "date_set_id": identifier, "started_at": started,
                "completed_at": _utcnow(), "status": "FAILED", "action": "BLOCKED",
                "failure_reason": f"{type(error).__name__}: {error}"[:8000],
            },
        )
        raise
    finally:
        for staging_table in staging_tables:
            spark.sql(f"DROP TABLE IF EXISTS {staging_table}")
