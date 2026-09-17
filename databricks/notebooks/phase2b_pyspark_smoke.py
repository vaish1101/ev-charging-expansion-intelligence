# Databricks notebook source
"""Synthetic Phase 2B gate for Databricks Express serverless PySpark."""

import json
import os

from pyspark.sql import SparkSession, functions as F


spark = SparkSession.getActiveSession()
assert spark is not None, "SparkSession is unavailable"

rows = [(1, "keep"), (2, "drop"), (3, "keep")]
frame = spark.createDataFrame(rows, "record_id INT, disposition STRING")
selected = frame.select("record_id", "disposition").filter(F.col("disposition") == "keep")

assert frame.count() == 3
assert selected.count() == 2
assert [row.record_id for row in selected.orderBy("record_id").collect()] == [1, 3]

catalog = dbutils.widgets.get("catalog")
os.environ["EV_CATALOG"] = catalog
table_name = f"{catalog}.audit._phase2b_pyspark_smoke"
spark.sql(f"DROP TABLE IF EXISTS {table_name}")
try:
    selected.write.format("delta").mode("overwrite").saveAsTable(table_name)
    assert spark.table(table_name).count() == 2
    detail = spark.sql(f"DESCRIBE DETAIL {table_name}").select("format", "name").first()
    assert detail.format == "delta"
    assert detail.name == table_name
finally:
    spark.sql(f"DROP TABLE IF EXISTS {table_name}")

dbutils.notebook.exit(
    json.dumps(
        {
            "spark_session": "available",
            "input_rows": 3,
            "filtered_rows": 2,
            "delta_round_trip": "passed",
            "cleanup": "passed",
        },
        sort_keys=True,
    )
)
