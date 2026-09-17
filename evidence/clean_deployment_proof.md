# Clean Deployment Proof

Validated 16 September 2026 against a fresh Databricks catalog and schema bootstrap.

| Check | Result | Evidence |
|---|---|---|
| Bundle validation | PASS | clean deployment execution record |
| Clean Bundle deployment | PASS | clean deployment execution record |
| Immutable source landing | PASS, 3 checksum-verified snapshots | clean deployment execution record |
| Six-task workflow | SUCCESS | successful workflow capture and dashboard evidence |
| Gold publication gate | PASS, 73 of 73 checks | dataset quality reference |
| Published analysis regions | 400 | `data/reference/regional_kpi_snapshot.csv` |
| Registered BEVs | 2,362,218 | `data/reference/dataset_quality.csv` |
| Registered passenger cars | 49,644,855 | `data/reference/dataset_quality.csv` |
| In-service facilities | 116,423 | `data/reference/dataset_quality.csv` |
| In-service points | 209,098 | `data/reference/dataset_quality.csv` |
| Normal points | 154,702 | `data/reference/dataset_quality.csv` |
| Fast points | 54,396 | `data/reference/dataset_quality.csv` |
| Unclassified points | 0 | `data/reference/dataset_quality.csv` |
| In-service registered facility nominal power | 9,086,313.500 kW | `data/reference/dataset_quality.csv` |
| Final dashboard datasets | 6 succeeded, 0 failed | `dashboard_evidence.json` |
| Final Page 2 default | München, Stadt, 1 regional row and 3 comparison rows | `dashboard_evidence.json` |

The final reference CSVs were rebuilt locally from the exact immutable source bytes and independently reproduced every locked national control. A final live SQL export was attempted on 17 September 2026, but the stopped serverless warehouse did not process the request. The portable CSVs therefore document the independently reproduced result, while [`databricks/sql/published_gold_views.sql`](../databricks/sql/published_gold_views.sql) preserves the exact source-controlled public view definitions.

No workspace host, organization ID, warehouse ID, job ID, run ID, dashboard ID or authenticated URL is retained in this public proof.
