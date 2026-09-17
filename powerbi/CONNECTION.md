# Power BI connection and refresh

The checked-in PBIP is configured for Import mode and reads only the two published Databricks Gold views. Its public TMDL contains placeholders rather than a live workspace endpoint.

## Required values

| Placeholder | Replace with |
|---|---|
| `DATABRICKS_SERVER_HOSTNAME` | Server hostname from the target SQL Warehouse connection details |
| `DATABRICKS_SQL_WAREHOUSE_ID` | SQL Warehouse identifier used in the HTTP path |
| `DATABRICKS_CATALOG` | Catalog created by the project Bundle/bootstrap process |

Replace the placeholders in:

- `EV Charging Intelligence.SemanticModel/definition/tables/Dataset.tmdl`
- `EV Charging Intelligence.SemanticModel/definition/tables/Regional KPI.tmdl`

Both partitions use schema `gold` and connector implementation `2.0`.

## Required access

- `CAN USE` on the selected SQL Warehouse.
- `USE CATALOG` and `USE SCHEMA` for the deployed catalog and `gold` schema.
- `SELECT` on `vw_powerbi_region_kpi_published` and `vw_powerbi_date_set_quality`.

Use OAuth with the appropriate organizational account during attended Power BI Desktop development. Do not store tokens, client secrets or exported credentials in the project.

## Refresh gate

Refresh only when the quality view reports:

- `publication_state = "published"`
- `power_bi_refresh_ready = true`
- `failed_dq_checks = 0`

The repository does not claim a Power BI Service deployment, gateway or scheduled refresh. Any future unattended refresh should use a narrowly scoped service principal and must keep credentials outside source control.

## Official guidance

- [Microsoft Databricks connector documentation](https://learn.microsoft.com/power-query/connectors/databricks)
- [Databricks Power BI integration documentation](https://docs.databricks.com/aws/en/partners/bi/power-bi)
