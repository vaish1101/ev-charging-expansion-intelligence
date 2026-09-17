-- Recreates the two published-only Gold serving views used by the dashboards.
-- These definitions are source controlled by src/ev_charging/gold_transformations.py.

CREATE OR REPLACE VIEW ev_analytics.gold.vw_powerbi_region_kpi_published AS
SELECT k.*, r.state AS publication_state, r.date_set_label
FROM ev_analytics.gold.gold_region_kpi_snapshot k
INNER JOIN ev_analytics.audit.date_set_registry r USING (date_set_id)
WHERE r.state = 'published';

CREATE OR REPLACE VIEW ev_analytics.gold.vw_powerbi_date_set_quality AS
WITH latest AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY date_set_id ORDER BY completed_at DESC, gold_run_id DESC
  ) AS row_number
  FROM ev_analytics.audit.gold_publication_run
  WHERE status = 'SUCCESS'
)
SELECT r.date_set_id,
       r.date_set_label,
       r.kba_reference_date,
       r.bnetza_reference_date,
       r.destatis_reference_date,
       r.state AS publication_state,
       l.gold_run_id,
       l.passed_dq_checks,
       l.failed_dq_checks,
       l.completed_at,
       CAST(62 AS INT) AS kba_to_bnetza_lag_days,
       CAST(l.failed_dq_checks = 0 AS BOOLEAN) AS power_bi_refresh_ready
FROM ev_analytics.audit.date_set_registry r
INNER JOIN latest l USING (date_set_id)
WHERE r.state = 'published' AND l.row_number = 1;
