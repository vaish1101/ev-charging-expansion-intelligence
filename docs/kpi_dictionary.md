# KPI Dictionary V1

**Status:** Revised for final Phase 1 sign-off  
**Core grain:** `analysis_region × date_set_id`  
**Scope:** Twelve descriptive KPIs; no composite score or regional-context KPI

## Common rules

- Every row has non-null `date_set_id`, binding exact sources, mappings, transformations and KPI version.
- BNetzA eligibility is exactly `Status == 'In Betrieb'`.
- Supply regions with no eligible facilities receive zero only after complete parsing and mapping prove absence. Missing, unmapped or quarantined input stays null with a quality reason and blocks publication.
- A missing KBA region remains on the 400-region scaffold with null demand and blocks publication.
- Ratios use unrounded inputs. A null or nonpositive denominator returns null with `invalid_denominator`, never zero or infinity.
- Counts are whole-number `BIGINT` values with no rounding.
- Percent and per-1,000 results are `DECIMAL(18,4)`, rounded half-up to four stored decimals and displayed to two decimals.
- Facility nominal power is parsed as decimal kW and summed once per unique eligible facility.
- Every serving view exposes `date_set_id`, KBA date, BNetzA date and Destatis geography date.

## KPI-01 : Registered BEV Passenger-Car Stock

- **KPI ID:** `KPI-01`.
- **Exact source fields:** KBA FZ 27.15 `C8:C12 → C Statistische Kennziffer`; `H10:K10 → J11:K11 → J12 → J Elektro (BEV)`.
- **Numerator/formula:** `SUM(J Elektro (BEV))`; current KBA records are already at target-region grain.
- **Denominator:** None.
- **Eligibility filters:** Five-digit KBA key; published non-negative integer BEV value; no disclosure marker.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `BIGINT`; registered BEV passenger cars; whole number; no rounding.
- **Null propagation:** Invalid, marked or missing BEV remains null and blocks publication.
- **Missing-region behavior:** Preserve the scaffold row with null and blocking quality status; never substitute zero.
- **Source/reference dates:** KBA 2026-07-01; bound BNetzA 2026-09-01 and Destatis 2026-06-30 remain exposed.
- **Known limitations:** Registered stock is a demand proxy, not registrations, observed charging demand, active use or vehicle movement.

## KPI-02 : Registered Passenger-Car Stock

- **KPI ID:** `KPI-02`.
- **Exact source fields:** KBA FZ 27.15 `C8:C12 → C Statistische Kennziffer`; `E8:E12 → E Anzahl insgesamt`.
- **Numerator/formula:** `SUM(E Anzahl insgesamt)`.
- **Denominator:** None.
- **Eligibility filters:** Five-digit KBA key; published non-negative integer; `total_pkw >= bev_stock`.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `BIGINT`; registered passenger cars; whole number; no rounding.
- **Null propagation:** Invalid, marked or missing total Pkw remains null and blocks publication.
- **Missing-region behavior:** Preserve the scaffold row with null and blocking quality status; never substitute zero.
- **Source/reference dates:** KBA 2026-07-01; bound BNetzA 2026-09-01 and Destatis 2026-06-30 remain exposed.
- **Known limitations:** Registered Pkw stock is not active utilization or vehicle movement.

## KPI-03 : BEV Penetration Among Passenger Cars (%)

- **KPI ID:** `KPI-03`.
- **Exact source fields:** KPI-01 KBA column J hierarchy and KPI-02 KBA column E hierarchy.
- **Numerator/formula:** `100 × registered_bev_stock / registered_total_pkw`.
- **Denominator:** Registered passenger-car stock from KPI-02.
- **Eligibility filters:** Both KBA inputs valid; denominator `> 0`.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `DECIMAL(18,4)`; percent; half-up to four stored decimals; display two.
- **Null propagation:** Either input null or denominator nonpositive returns null with reason.
- **Missing-region behavior:** Preserve the scaffold row with null and blocking quality status.
- **Source/reference dates:** Numerator and denominator use KBA 2026-07-01; bound BNetzA/Destatis dates remain exposed.
- **Known limitations:** Registered adoption share does not measure charging behavior, causal demand or infrastructure need.

## KPI-04 : In-Service Registered Charging Facilities

- **KPI ID:** `KPI-04`.
- **Exact source fields:** BNetzA `Ladeeinrichtungs-ID`, `Status` and governed raw-district mapping inputs.
- **Numerator/formula:** `COUNT_DISTINCT(Ladeeinrichtungs-ID) WHERE Status = 'In Betrieb'`.
- **Denominator:** None.
- **Eligibility filters:** Facility key valid and unique within the bound BNetzA revision; exact in-service status; trusted regional mapping.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `BIGINT`; registered charging facilities; whole number; no rounding.
- **Null propagation:** Any unresolved facility or mapping quarantine blocks publication until reconciled.
- **Missing-region behavior:** Use zero only after complete validation proves no eligible facility; otherwise null and block.
- **Source/reference dates:** BNetzA 2026-09-01; KBA 2026-07-01 and Destatis 2026-06-30 remain exposed.
- **Known limitations:** A registered facility is not a proven unique physical site; the register can omit pending or unreported infrastructure.

## KPI-05 : In-Service Registered Charging Points

- **KPI ID:** `KPI-05`.
- **Exact source fields:** BNetzA `Ladeeinrichtungs-ID`, `Status`, `Anzahl Ladepunkte`, `Steckertypen1..6` and governed regional mapping inputs.
- **Numerator/formula:** `SUM(Anzahl Ladepunkte) WHERE Status = 'In Betrieb'`, only after each declared count equals its populated-slot count.
- **Denominator:** None.
- **Eligibility filters:** Eligible parent facility; trusted regional mapping; valid declared-to-derived point reconciliation.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `BIGINT`; registered charging points; whole number; no rounding.
- **Null propagation:** Unresolved regional point quarantine remains null and blocks publication.
- **Missing-region behavior:** Use zero only after complete validation proves no eligible point; otherwise null and block.
- **Source/reference dates:** BNetzA 2026-09-01; KBA 2026-07-01 and Destatis 2026-06-30 remain exposed.
- **Known limitations:** Counts registered points on in-service facilities; connector tokens are not additional points and publication may be incomplete.

## KPI-06 : In-Service Registered Normal Charging Points

- **KPI ID:** `KPI-06`.
- **Exact source fields:** BNetzA `Ladeeinrichtungs-ID`, `Status`, `Steckertypen1..6`, `Nennleistung Stecker1..6` and governed regional mapping inputs.
- **Numerator/formula:** Count populated point slots on in-service facilities where maximum parsed connector nominal power for the slot is `<= 22 kW`.
- **Denominator:** None.
- **Eligibility filters:** Exact in-service status; trusted region; populated `Steckertypen<n>`; all required slot power tokens parse.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `BIGINT`; registered normal charging points; whole number; no rounding.
- **Null propagation:** An unclassified/quarantined point stays separate and blocks publication until reconciled.
- **Missing-region behavior:** Use zero only after complete validation proves no eligible normal point; otherwise null and block.
- **Source/reference dates:** BNetzA 2026-09-01; KBA 2026-07-01 and Destatis 2026-06-30 remain exposed.
- **Known limitations:** Classification uses the approved point threshold; facility class and AC/DC labels cannot replace the rule.

## KPI-07 : In-Service Registered Fast Charging Points

- **KPI ID:** `KPI-07`.
- **Exact source fields:** BNetzA `Ladeeinrichtungs-ID`, `Status`, `Steckertypen1..6`, `Nennleistung Stecker1..6` and governed regional mapping inputs.
- **Numerator/formula:** Count populated point slots on in-service facilities where maximum parsed connector nominal power for the slot is `> 22 kW`.
- **Denominator:** None.
- **Eligibility filters:** Exact in-service status; trusted region; populated `Steckertypen<n>`; all required slot power tokens parse.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `BIGINT`; registered fast charging points; whole number; no rounding.
- **Null propagation:** An unclassified/quarantined point stays separate and blocks publication until reconciled.
- **Missing-region behavior:** Use zero only after complete validation proves no eligible fast point; otherwise null and block.
- **Source/reference dates:** BNetzA 2026-09-01; KBA 2026-07-01 and Destatis 2026-06-30 remain exposed.
- **Known limitations:** Classification uses the approved point threshold and does not measure delivered power or utilization.

## KPI-08 : Registered Cumulative Nominal Power of In-Service Charging Facilities (kW)

- **KPI ID:** `KPI-08`.
- **Exact source fields:** BNetzA `Ladeeinrichtungs-ID`, `Status`, `Nennleistung Ladeeinrichtung [kW]` and governed regional mapping inputs.
- **Numerator/formula:** `SUM(Nennleistung Ladeeinrichtung [kW]) WHERE Status = 'In Betrieb'`, once per unique facility in the bound revision.
- **Denominator:** None.
- **Eligibility filters:** Valid unique facility; exact in-service status; trusted region; positive parseable facility nominal kW.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `DECIMAL(20,3)`; kW; retain exact parsed aggregate; no calculation rounding; display one decimal for the current revision.
- **Null propagation:** Invalid facility power is quarantined; the affected date set cannot publish until accepted plus quarantined power reconciles.
- **Missing-region behavior:** Use exact `0.000 kW` only after complete validation proves no eligible facility; otherwise null and block.
- **Source/reference dates:** BNetzA 2026-09-01; KBA 2026-07-01 and Destatis 2026-06-30 remain exposed.
- **Known limitations:** Current national control is 9,086,313.5 kW. This is registered cumulative facility nominal power:not grid capacity, simultaneous deliverable power, site connection capacity, energy or utilization.

## KPI-09 : In-Service Registered Charging Points per 1,000 BEVs

- **KPI ID:** `KPI-09`.
- **Exact source fields:** KPI-05 BNetzA point fields and KPI-01 KBA column J hierarchy.
- **Numerator/formula:** `1,000 × in_service_registered_points / registered_bev_stock`.
- **Denominator:** Registered BEV passenger-car stock from KPI-01.
- **Eligibility filters:** Governed KPI-05 numerator; governed KPI-01 denominator `> 0`; both bound to the same `date_set_id`.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `DECIMAL(18,4)`; points per 1,000 BEVs; half-up to four stored decimals; display two.
- **Null propagation:** Null input or nonpositive denominator returns null with reason.
- **Missing-region behavior:** Validated zero supply returns `0.0000`; missing/invalid demand remains null and blocks.
- **Source/reference dates:** KBA 2026-07-01 and BNetzA 2026-09-01; Destatis 2026-06-30; 62-day KBA-to-BNetzA lag displayed.
- **Known limitations:** A registered provision ratio, not observed demand, utilization, required deployment or optimal supply.

## KPI-10 : In-Service Registered Fast Charging Points per 1,000 BEVs

- **KPI ID:** `KPI-10`.
- **Exact source fields:** KPI-07 BNetzA point/power fields and KPI-01 KBA column J hierarchy.
- **Numerator/formula:** `1,000 × in_service_registered_fast_points / registered_bev_stock`.
- **Denominator:** Registered BEV passenger-car stock from KPI-01.
- **Eligibility filters:** Governed KPI-07 numerator; governed KPI-01 denominator `> 0`; both bound to the same `date_set_id`.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `DECIMAL(18,4)`; fast points per 1,000 BEVs; half-up to four stored decimals; display two.
- **Null propagation:** Null input, unclassified point dependency or nonpositive denominator returns null with reason.
- **Missing-region behavior:** Validated zero fast supply returns `0.0000`; missing/invalid demand remains null and blocks.
- **Source/reference dates:** KBA 2026-07-01 and BNetzA 2026-09-01; Destatis 2026-06-30; 62-day KBA-to-BNetzA lag displayed.
- **Known limitations:** Uses the approved `> 22 kW` point threshold; does not measure delivered power, demand, utilization or required deployment.

## KPI-11 : In-Service Registered Charging Facilities per 1,000 BEVs

- **KPI ID:** `KPI-11`.
- **Exact source fields:** KPI-04 BNetzA facility fields and KPI-01 KBA column J hierarchy.
- **Numerator/formula:** `1,000 × in_service_registered_facilities / registered_bev_stock`.
- **Denominator:** Registered BEV passenger-car stock from KPI-01.
- **Eligibility filters:** Governed KPI-04 numerator; governed KPI-01 denominator `> 0`; both bound to the same `date_set_id`.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `DECIMAL(18,4)`; facilities per 1,000 BEVs; half-up to four stored decimals; display two.
- **Null propagation:** Null input or nonpositive denominator returns null with reason.
- **Missing-region behavior:** Validated zero supply returns `0.0000`; missing/invalid demand remains null and blocks.
- **Source/reference dates:** KBA 2026-07-01 and BNetzA 2026-09-01; Destatis 2026-06-30; 62-day KBA-to-BNetzA lag displayed.
- **Known limitations:** Facilities are not proven unique sites; ratio does not measure observed demand, utilization or required deployment.

## KPI-12 : Registered Nominal Power of In-Service Charging Facilities per 1,000 BEVs

- **KPI ID:** `KPI-12`.
- **Exact source fields:** KPI-08 BNetzA facility nominal-power fields and KPI-01 KBA column J hierarchy.
- **Numerator/formula:** `1,000 × registered_cumulative_nominal_power_in_service_kw / registered_bev_stock`.
- **Denominator:** Registered BEV passenger-car stock from KPI-01.
- **Eligibility filters:** Governed KPI-08 numerator; governed KPI-01 denominator `> 0`; both bound to the same `date_set_id`.
- **Grain / key / date_set_id:** One `analysis_region × date_set_id`; `(date_set_id, analysis_region_sk)`; ID is mandatory.
- **Output type / unit / precision / rounding:** `DECIMAL(18,4)`; **kW per 1,000 BEVs**; half-up to four stored decimals; display two.
- **Null propagation:** Null input, quarantined power or nonpositive denominator returns null with blocking reason.
- **Missing-region behavior:** Validated zero supply returns `0.0000 kW per 1,000 BEVs`; missing/invalid demand remains null and blocks.
- **Source/reference dates:** KBA 2026-07-01 and BNetzA 2026-09-01; Destatis 2026-06-30; 62-day KBA-to-BNetzA lag displayed.
- **Known limitations:** Relative registered facility nominal power:not grid capacity, site capacity, simultaneous delivery, energy, utilization or a deployment prescription.

## Deferred and prohibited in Core V1

Population, area, density, urbanisation and all `fact_regional_context`/`gold_regional_context` concepts are **DEFERRED FROM CORE V1**. Exact territorial inclusion and context aggregation are not frozen. Raw Destatis cells remain evidence for a later gated extension.

Also prohibited:

- unqualified “charging capacity”;
- point/connector power sums as capacity;
- inferred unique sites;
- municipality-level adequacy;
- composite infrastructure-gap, priority or investment score;
- causal demand, optimal siting, required quantities, ROI or grid-feasibility claims.
