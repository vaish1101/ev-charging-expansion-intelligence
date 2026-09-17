# Methodology

This project screens German regions where registered public charging provision is comparatively low relative to registered battery electric passenger-car stock. It supports prioritization for further analysis, not an automatic investment decision. The [README](../README.md) presents the business findings; this document records the analytical method and its limits.

## Source selection and dates

The publication combines three official sources:

- KBA FZ 27.15 provides absolute registered passenger-car and BEV stock for 400 Zulassungsbezirk records at 1 July 2026.
- The BNetzA Ladesäulenregister provides one registered Ladeeinrichtung per source row at 1 September 2026, including status, charging-point slots and facility nominal power.
- Destatis GV-ISys provides the current administrative reference at 30 June 2026.

The KBA stock date precedes the BNetzA infrastructure date by 62 days. The resulting comparison is a labelled cross-sectional screen, not a simultaneous market balance. Each approved file is bound to a size and SHA-256 checksum. A `date_set_id` hashes the exact source revisions, geography rules, transformation version and KPI definition version.

## Analytical grain

KBA FZ 27.15 defines the demand grain: one Zulassungsbezirk and reference date. Its `Elektro (BEV)` field is an absolute integer stock, not a percentage or registration flow. BEV stock is the primary demand proxy because BEVs depend fully on charging; plug-in hybrid stock remains available in lineage but is not included in the V1 denominator.

The final analytical layer contains 400 KBA-aligned analysis regions. These units closely resemble districts but are not described as 400 current administrative Kreise because the source systems do not align one-to-one.

## Geography reconciliation

Current Destatis geography contains 401 districts. Every district is accounted for through a governed bridge:

- Trier city (`07211`) and Trier-Saarburg (`07235`) aggregate upward into KBA analysis region `07211`. KBA demand is never allocated downward.
- Hanau is handled as an effective-dated change. Current district `06415` is valid from 1 January 2026, while the historical municipality and Main-Kinzig-Kreis relationship remains preserved in the rules.
- The remaining current districts map one-to-one to their analysis regions.

BNetzA district/state labels first reconcile to current Destatis district codes, then to the KBA-aligned analysis region. Postal codes and fuzzy name matching are not canonical join keys. Unmatched or ambiguous records fail quality controls rather than disappearing in an inner join.

## Charging infrastructure semantics

A BNetzA row is one registered Ladeeinrichtung. Up to six populated point slots create charging-point records. Connector descriptions belong to a point and do not create additional points.

Operational metrics include only facilities where `Status = 'In Betrieb'`. The 20 `In Wartung` facilities, their 38 points and 484.000 kW remain in Bronze, Silver and reconciliation evidence but are excluded from operational numerators.

Each populated point is classified using its maximum parsed connector rating. A point at or below 22 kW is normal; a point above 22 kW is fast. The approved snapshot contains 154,702 in-service normal points and 54,396 in-service fast points, with zero unclassified operational points.

`registered_facility_nominal_power_kw` is the parsed BNetzA facility-level nominal-power field. It is summed once per eligible facility and reported as registered cumulative nominal power. It is not grid capacity, site connection capacity, simultaneous deliverable power, energy or utilization. Point and connector ratings are never summed to create this facility measure.

## KPIs and regional benchmarks

The Gold layer retains both scale and normalized provision:

- registered BEV and passenger-car stock;
- BEV penetration among registered passenger cars;
- in-service registered facilities, total points, normal points and fast points;
- registered facility nominal power;
- facilities, total points, fast points and nominal power per 1,000 registered BEVs.

Per-1,000-BEV measures use strictly positive BEV stock from the same `date_set_id`. Regional medians are descriptive benchmarks because the distributions are right-skewed. They are not policy targets, service standards or required infrastructure levels.

BEV stock is also the denominator of the normalized provision measures. A scatter that places BEV stock against points per 1,000 BEVs is therefore a screening view, not evidence of correlation or causation. Absolute and normalized measures remain separate so that small denominators do not dominate interpretation.

No composite score is published. A weighted score would hide subjective choices and appear more prescriptive than the available evidence supports.

## Publication controls

The workflow lands and verifies the three immutable snapshots, checks the frozen parsing contracts, builds Bronze and Silver, creates isolated Gold candidates, runs 73 blocking checks, and publishes only when every check passes. The existing published layer remains unchanged after a failed candidate. Repeating the same approved inputs is idempotent and returns a no-op after content validation.

The dashboard reads only the published Gold serving views. Candidate tables, Bronze data and Silver entities are not exposed to it.

## Interpretation and limitations

The screen identifies regions that warrant further investigation. It cannot establish charging demand, required charger quantities, optimal sites, grid feasibility or return on investment. The current data does not include utilization, reliability, queues, traffic, private charging, competitive coverage, accessibility, parcels, grid connections, capital cost, operating cost or revenue.

The publication is cross-sectional, so no predictive model is used. Historical snapshots, a defensible target variable and time-aware validation would be required before forecasting. The next evidence to add is utilization and reliability, followed by traffic, competitive and site coverage, grid feasibility and commercial economics.

## Deployment scope

The implemented portfolio environment is Databricks Express with serverless compute, Unity Catalog and Databricks-managed storage. The same logical contracts can later move to Azure Databricks with ADLS Gen2, Microsoft Entra identities, networking, secrets, monitoring and environment promotion. Those Azure infrastructure controls are future extensions and are not claimed as implemented here.
