# EV Charging Expansion Intelligence

Identifies German regions where registered public charging provision is comparatively low relative to registered battery electric vehicle adoption, using official KBA, BNetzA and Destatis data.

![Power BI Executive and Regional Screening](dashboards/powerbi/executive-regional-screening.png)

*Compares market scale with total and fast public charging provision across 400 analysis regions.*

| 400 | 2.36M | 209.1K | 73/73 |
|---:|---:|---:|---:|
| analysis regions | registered BEVs | in-service charging points | blocking checks passed |

[View the dashboard demo](assets/demo/ev_charging_demo.mp4) · [Architecture](docs/architecture.md) · [Methodology](docs/methodology.md) · [KPI dictionary](docs/kpi_dictionary.md) · [Reproduction](docs/reproduction.md)

## Business problem

National totals do not show whether public charging provision is distributed in line with regional EV adoption. Network planning and commercial analytics teams need to compare market size with provision relative to the local EV base before deciding where deeper analysis is worthwhile.

This project asks which German regions have comparatively low registered public charging provision relative to registered BEV stock. It does not estimate charging demand, required charger quantities, optimal sites, grid feasibility or investment returns.

## Key findings

- Germany has **2,362,218 registered BEVs** and **209,098 in-service public charging points** in the selected snapshot.
- **53 of the 100 largest BEV markets** are below both the regional total and fast charging provision medians.
- **München, Stadt** has the largest BEV stock at 62,153 but sits below both medians, with 58.95 total and 7.19 fast points per 1,000 BEVs.
- **Stuttgart** has high total provision but low fast provision, showing why charging mix matters alongside total point counts.
- **Euskirchen** has the lowest total provision ratio in the snapshot at 31.68 points per 1,000 BEVs.

BEV stock is both a measure of market scale and the denominator of the per-1,000-BEV metrics. These are screening comparisons, not causal or correlation analyses.

## Where to investigate next

| Region or pattern | What the data shows | Recommended next analysis |
|---|---|---|
| München, Stadt | Largest BEV market and below both provision medians | Test utilization, traffic, competitor coverage, site availability, grid feasibility and economics |
| Stuttgart | High total provision and low fast provision | Investigate fast charging use cases and corridor demand |
| Euskirchen | Lowest total provision ratio | Validate utilization, access and network coverage before drawing conclusions |
| Rhein-Neckar-Kreis | Large BEV market below the total provision median | Compare traffic, competitive coverage and feasible sites |
| Top 100 BEV markets | 53 regions below both medians | Use the cohort as a shortlist for deeper commercial screening |

These are recommended next analyses, not investment recommendations.

## How I solved it

I combined three official German datasets into a consistent 400-region analytical model using Databricks, PySpark, Spark SQL and Delta Lake. The workflow validates each source, builds Bronze, Silver and Gold layers, applies blocking quality checks, and publishes data for reporting only after every check passes.

The main technical challenge was geography. KBA reports 400 vehicle-registration regions, current Destatis geography contains 401 districts, and BNetzA provides district labels rather than the KBA regional key. The reconciliation model accounts for every current district, including Trier's two-to-one aggregation and Hanau's administrative transition.

**Stack:** Databricks, PySpark, Spark SQL, Delta Lake, Unity Catalog, Power BI, DAX, Python, Pytest and GitHub Actions.

## Technical achievements

- Unified KBA, BNetzA and Destatis data into a consistent 400-region model.
- Resolved the 401-to-400 geography mismatch without silently dropping unmatched records.
- Built reproducible Bronze, Silver and Gold transformations with publication quality gates.
- Defined 12 reusable business KPIs covering EV adoption, infrastructure and provision per 1,000 BEVs.
- Served the same validated KPI layer to Databricks AI/BI and Power BI.
- Added automated checks for source contracts, geography, KPI calculations and publication integrity.

## System architecture

![System architecture](assets/architecture/system_architecture.svg)

Bronze preserves the downloaded source structure. Silver resolves entities and geography. Gold calculates the regional KPIs and publishes only validated results. Both dashboards use the published reporting views.

See [Architecture](docs/architecture.md) for the geography reconciliation and publication-control flows.

## Dashboards

### Databricks AI/BI

The Databricks dashboard supports national screening and region-level benchmarking using validated published Gold data.

![Databricks Germany Market and Provision Screening](dashboards/databricks/01_germany_market_provision_screening.png)

![Databricks München Region Profile](dashboards/databricks/02_region_profile_munich.png)

[Workflow success](dashboards/databricks/03_workflow_success.png) · [Dashboard PDF](dashboards/databricks/databricks-dashboard.pdf)

### Power BI

Power BI provides a two-page executive view for regional screening and region-level investigation, built against the same KPI layer as the Databricks dashboard.

![Power BI Region Profile](dashboards/powerbi/region-profile.png)

[Power BI project guide](powerbi/README.md) · [Dashboard PDF](dashboards/powerbi/power-bi-dashboard.pdf)

## Data quality and engineering

- Exact source revisions are bound to filenames, sizes and SHA-256 checksums.
- A controlled geography bridge reconciles all 401 current districts to 400 analysis regions.
- Gold publication is blocked when any quality check fails.
- Controlled schema and checksum failures were rejected while the prior published result remained unchanged.

The final controls reconcile to 400 regions, 2,362,218 BEVs and 209,098 charging points. See [Data quality](docs/data_quality.md) for the full control framework.

## Limitations

- Registered BEV stock is a market proxy, not observed charging demand.
- The BNetzA register does not provide utilization, reliability or queueing.
- Source dates differ by up to 62 days.
- The snapshot is cross-sectional and cannot support trend, forecast or causal claims.
- Traffic, private charging, competitor coverage, site constraints, grid feasibility, cost and revenue are not included.

## Data sources

| Source | Reference date | Role in the analysis | Source grain |
|---|---|---|---|
| KBA FZ 27.15 | 1 July 2026 | Registered passenger-car and BEV stock | One Zulassungsbezirk |
| BNetzA Ladesäulenregister | 1 September 2026 | Registered public charging facilities and points | One Ladeeinrichtung |
| Destatis GV-ISys | 30 June 2026 | Current district codes and names | One administrative unit |

Raw provider files are not redistributed. Source URLs, filenames, sizes and checksums are recorded in [`data/source_manifest.json`](data/source_manifest.json). Detailed definitions are available in the [Methodology](docs/methodology.md) and [KPI dictionary](docs/kpi_dictionary.md).

## Reproduction

Reproduction, source acquisition and deployment instructions are available in [docs/reproduction.md](docs/reproduction.md).

## License and data attribution

Project source code is licensed under [MIT](LICENSE). Provider data is not covered by the MIT license and is not redistributed.

- **KBA:** Kraftfahrt-Bundesamt, FZ 27.15, reference date 1 July 2026; Datenlizenz Deutschland Namensnennung 2.0.
- **BNetzA:** Bundesnetzagentur.de, Ladesäulenregister, reference date 1 September 2026; CC BY 4.0.
- **Destatis:** © Statistisches Bundesamt (Destatis), GV-ISys, administrative status 30 June 2026. Reproduction and distribution are permitted with source attribution under the notice carried by the approved workbook.

See [`data/README.md`](data/README.md) for source pages, license links and attribution requirements.
