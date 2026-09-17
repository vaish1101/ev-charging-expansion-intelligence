# Reproduction

## Local validation

Use Python 3.12.

```bash
python -m pip install -r requirements.txt
pytest -q --ignore=tests/test_approved_source_conformance.py
python scripts/validate_public_release.py
```

The exact-source conformance test is intentionally excluded from public CI because the provider files are not redistributed. It runs locally after the three approved files are placed under `data/raw/`.

## Obtain the official files

Follow [`../data/README.md`](../data/README.md) and save the exact files at the paths recorded in `data/source_manifest.json`. Verify every checksum before deployment.

## Prepare a Databricks workspace

You need an authenticated Databricks CLI profile, permission to create a Unity Catalog catalog and schemas, and an existing SQL Warehouse.

```bash
python scripts/bootstrap_databricks.py \
  --profile YOUR_PROFILE \
  --warehouse-id YOUR_WAREHOUSE_ID \
  --catalog YOUR_CATALOG

python scripts/prepare_bundle.py --catalog YOUR_CATALOG

databricks bundle validate \
  --profile YOUR_PROFILE \
  --var="catalog=YOUR_CATALOG" \
  --var="warehouse_id=YOUR_WAREHOUSE_ID"

databricks bundle deploy \
  --profile YOUR_PROFILE \
  --var="catalog=YOUR_CATALOG" \
  --var="warehouse_id=YOUR_WAREHOUSE_ID"

databricks bundle run ev_charging_pipeline \
  --profile YOUR_PROFILE \
  --var="catalog=YOUR_CATALOG" \
  --var="warehouse_id=YOUR_WAREHOUSE_ID"
```

The bootstrap is idempotent. It creates the catalog, schemas and managed landing Volume. The Bundle uploads checksum-verified sources, deploys notebooks and the six-task workflow, and renders a catalog-specific dashboard from the source-controlled template.

## Validate published output

```bash
python scripts/validate_gold_controls.py \
  --profile YOUR_PROFILE \
  --warehouse-id YOUR_WAREHOUSE_ID \
  --catalog YOUR_CATALOG

python scripts/validate_dashboard_queries.py \
  --profile YOUR_PROFILE \
  --warehouse-id YOUR_WAREHOUSE_ID \
  --catalog YOUR_CATALOG
```

Expected controls are listed in [data_quality.md](data_quality.md). The two dashboard views must return 400 regional rows and one published quality row.

## Open Power BI

On Windows, open [`../powerbi/EV Charging Intelligence.pbip`](../powerbi/EV%20Charging%20Intelligence.pbip) in Power BI Desktop. Keep the adjacent `.Report` and `.SemanticModel` folders in place. Replace the documented connection placeholders with your own Databricks host, SQL Warehouse ID and catalog before refresh. No credentials are included in the project.
