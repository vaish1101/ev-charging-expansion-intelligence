# Power BI semantic model

The executable semantic model is included as TMDL under `EV Charging Intelligence.SemanticModel/`. It contains four tables, two active one-to-many relationships and 74 explicit measures. The public partition expressions use connection placeholders; see `CONNECTION.md` before refresh.

## Model

```text
Analysis Region (400)  1 ──── *  Regional KPI (400 per date set)  * ──── 1  Dataset (1 current)
```

Both relationships are active, one-to-many, and single-direction from dimension to fact. There are no fact-to-fact, bidirectional, or many-to-many relationships.

### `Regional KPI`

- Source: `<catalog>.gold.vw_powerbi_region_kpi_published`.
- Grain/key: `(date_set_id, analysis_region_sk)`.
- Storage: Import.
- Purpose: governed regional measures and KPI results.
- Current expected rows: 400.

Do not aggregate the four per-1,000 columns or regional BEV penetration with `SUM`. Use the supplied `SELECTEDVALUE` measures for one-region visuals and the supplied iterator measures for regional medians.

### `Analysis Region`

- Source: a distinct, folding-friendly projection of the three region columns from `Regional KPI`.
- Grain/key: `analysis_region_sk`.
- Current expected rows: 400.
- User fields: `analysis_region_display_name`, `analysis_region_name`, `analysis_region_code`. Use the display field in visuals; retain the canonical source name for traceability.

Hide the surrogate key. Sort display names by region code only when deterministic ordering is needed. Do not infer a federal-state field from code prefixes and do not use region names for automatic map geocoding.

### `Dataset`

- Source: `<catalog>.gold.vw_powerbi_date_set_quality`.
- Grain/key: `date_set_id`.
- Current expected rows: one.
- Purpose: source dates, publication state, 62-day lag, run identity, DQ counts, and refresh readiness.

## Relationships

| From | To | Cardinality | Direction |
|---|---|---|---|
| `Analysis Region[analysis_region_sk]` | `Regional KPI[analysis_region_sk]` | 1:* | Single |
| `Dataset[date_set_id]` | `Regional KPI[date_set_id]` | 1:* | Single |

Validate after refresh that both one-side keys are unique and nonblank, the fact has 400 unique composite keys for the current date set, and both relationships match every fact row.

## Field presentation

Use display folders `Demand`, `Supply: Counts`, `Supply: Registered Nominal Power`, `Provision per 1,000 BEVs`, `Benchmarks`, `Exploratory Sorting`, and `Data Quality`.

Recommended formats:

| Field type | Format |
|---|---|
| Counts | `#,0` |
| Gold BEV penetration percent-points | `0.00\%` |
| Per-1,000 measures | `#,0.00` |
| Facility nominal power | `#,0.0 "kW"` |
| Presentation fast share | `0.00%` |
| National BEV Penetration (true national ratio) | `0.00%` |
| Relative (%) deltas vs regional median | `0.00%;-0.00%;0.00%` |
| Dates | `dd MMM yyyy` |

The Gold penetration value `4.4650` means 4.4650 percent. Do not apply Power BI's ordinary percentage format to the raw value, because that would multiply it by 100. `National BEV Penetration` is a separate measure using a plain ratio computed as `DIVIDE(SUM of BEVs, SUM of passenger cars)`. It uses the ordinary percentage format because it is not the Gold percent-point column. Do not confuse the two, and do not average or SELECTEDVALUE the regional `BEV Penetration` values to approximate a national figure.

Hide technical fact fields after measures are created: region keys duplicated from the dimension, `date_set_id`, denominator-quality reason, `kpi_12_unit`, `quality_status`, `publication_state`, and `date_set_label`. Keep quality and lineage values accessible through the `Dataset` table and the Methodology & Definitions bookmark panel.

## Calculation ownership

- Databricks Gold owns all 12 governed KPIs, source filtering, maintenance exclusion, point classification, geography, ratios, precision, and rounding.
- DAX supplies additive display wrappers, selected-region retrieval, **Regional Median** benchmarks, absolute and relative comparison deltas, a true national BEV-penetration rollup (`National BEV Penetration`, an additive `DIVIDE` of the two Gold base sums at a different grain from the per-region KPI-03 column), transparent BEV-stock rank and Top-100 screening measures, role-based scatter color, single-metric exploratory ranks, labels, and the explicitly non-governed presentation-only fast share.
- No composite score, cross-source transformation, source correction, or alternative KPI formula exists in the model.
- The two visible pages, Page 1 region controls, Page 2 default region and drillthrough/Back behavior, visual formatting, and the Methodology & Definitions bookmark panel are report-layer (`REPORT_SPEC.md`) concerns only. They do not change the semantic model.

## Benchmark filter context

The benchmark measures use `CALCULATETABLE(VALUES(Analysis Region[analysis_region_sk]), REMOVEFILTERS(Analysis Region))`. This removes all selected-region, page-slicer, and drillthrough filters from the Analysis Region dimension while preserving the active Dataset/date-set filter and its propagation to `Regional KPI`. The benchmark therefore stays fixed across region selections for one published date set but is not detached from dataset identity.

The four relative-delta measures are presentation comparisons only:

`(selected regional value - regional median) / regional median`

They do not create or replace governed KPIs. BEV penetration instead uses an absolute percentage-point difference because that is easier to interpret and avoids mixing the Gold percent-point convention with fractional percentage formatting.

## Presentation names

`powerbi/power_query/Analysis Region.m` keeps `analysis_region_name` and canonical keys unchanged and adds a presentation-only label using deterministic comma-aware title-casing plus seven documented code-keyed corrections for official abbreviations/transliterations. Examples include `München, Stadt`, `Düsseldorf, Stadt`, and `Rheinisch-Bergischer Kreis`. The display label is never a join key.
