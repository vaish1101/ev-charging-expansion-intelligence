import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_public_analysis_summary_matches_final_controls() -> None:
    summary = load_json("evidence/analysis_summary.json")
    assert summary["project_status"] == "complete"
    assert summary["analysis_regions"] == 400
    assert summary["registered_bevs"] == 2362218
    assert summary["in_service_charging_points"] == 209098
    assert summary["top_100_bev_markets_below_both_provision_medians"] == 53
    assert summary["gold_blocking_checks"] == {"passed": 73, "failed": 0}
    assert summary["dashboard_pages"] == {"databricks": 2, "power_bi": 2}


def test_final_pbip_source_is_present_without_pbix_claim() -> None:
    assert (ROOT / "powerbi/EV Charging Intelligence.pbip").is_file()
    assert (ROOT / "powerbi/EV Charging Intelligence.Report").is_dir()
    assert (ROOT / "powerbi/EV Charging Intelligence.SemanticModel").is_dir()
    assert not list(ROOT.glob("**/*.pbix"))


def test_semantic_model_has_only_dimension_to_fact_relationships() -> None:
    model = load_json("powerbi/model_contract.json")
    assert model["connection"]["storage_mode"] == "Import"
    assert model["imported_gold_objects"] == [
        "<catalog>.gold.vw_powerbi_region_kpi_published",
        "<catalog>.gold.vw_powerbi_date_set_quality",
    ]
    assert model["connection"]["server_hostname_placeholder"] == "DATABRICKS_SERVER_HOSTNAME"
    assert model["connection"]["http_path_placeholder"] == "DATABRICKS_SQL_WAREHOUSE_ID"
    assert model["connection"]["catalog_placeholder"] == "DATABRICKS_CATALOG"
    assert {table["role"] for table in model["semantic_tables"]} == {
        "fact",
        "dimension",
        "dimension_and_quality_metadata",
    }
    assert all(item["cardinality"] == "one_to_many" for item in model["relationships"])
    assert all(item["filter_direction"] == "single" for item in model["relationships"])
    assert model["model_rules"] == {
        "fact_to_fact_relationships": 0,
        "bidirectional_relationships": 0,
        "many_to_many_relationships": 0,
        "facility_or_point_detail_imported": False,
        "governed_kpi_formulas_reimplemented_in_dax": False,
        "composite_priority_score": False,
    }


def test_model_maps_all_twelve_governed_kpis() -> None:
    model = load_json("powerbi/model_contract.json")
    ids = [field["kpi_id"] for field in model["business_fields"] if "kpi_id" in field]
    assert ids == [f"KPI-{number:02d}" for number in range(1, 13)]


def test_power_query_uses_published_gold_only() -> None:
    regional = (ROOT / "powerbi/power_query/Regional KPI.m").read_text(encoding="utf-8")
    dataset = (ROOT / "powerbi/power_query/Dataset.m").read_text(encoding="utf-8")
    region = (ROOT / "powerbi/power_query/Analysis Region.m").read_text(encoding="utf-8")
    combined = regional + dataset + region
    assert "vw_powerbi_region_kpi_published" in regional
    assert "vw_powerbi_date_set_quality" in dataset
    assert '#"Regional KPI"' in region
    assert "analysis_region_display_name" in region
    assert "München, Stadt" in region
    assert "Rheinisch-Bergischer Kreis" in region
    assert "DatabricksServerHostname" in regional
    assert "DatabricksHttpPath" in regional
    assert "DatabricksCatalog" in regional
    assert "bronze" not in combined.lower()
    assert "silver" not in combined.lower()


def test_dax_keeps_governed_ratios_as_thin_wrappers() -> None:
    dax = (ROOT / "powerbi/measures.dax").read_text(encoding="utf-8")
    expected_measures = [
        "Registered BEVs :=",
        "Registered Passenger Cars :=",
        "BEV Penetration :=",
        "In-Service Charging Facilities :=",
        "In-Service Charging Points :=",
        "In-Service Normal Charging Points :=",
        "In-Service Fast Charging Points :=",
        "Registered Nominal Power of In-Service Charging Facilities :=",
        "Charging Points per 1,000 BEVs :=",
        "Fast Charging Points per 1,000 BEVs :=",
        "Charging Facilities per 1,000 BEVs :=",
        "Registered Nominal Power per 1,000 BEVs :=",
    ]
    assert all(measure in dax for measure in expected_measures)
    assert "SELECTEDVALUE ( 'Regional KPI'[bev_penetration_percent] )" in dax
    assert "SELECTEDVALUE ( 'Regional KPI'[in_service_registered_charging_points_per_1000_bevs] )" in dax
    assert "Presentation - Fast Share of In-Service Points" in dax
    assert "National BEV Penetration :=" in dax
    assert "DIVIDE ( [Registered BEVs], [Registered Passenger Cars] )" in dax


def test_dax_regional_benchmarks_preserve_dataset_context() -> None:
    dax = (ROOT / "powerbi/measures.dax").read_text(encoding="utf-8")
    expected = [
        "Regional Median - BEV Penetration :=",
        "Regional Median - Charging Points per 1,000 BEVs :=",
        "Regional Median - Fast Charging Points per 1,000 BEVs :=",
        "Regional Median - Charging Facilities per 1,000 BEVs :=",
        "Regional Median - Registered Nominal Power per 1,000 BEVs :=",
    ]
    assert all(measure in dax for measure in expected)
    assert "National Median" not in dax
    assert dax.count("REMOVEFILTERS ( 'Analysis Region' )") >= 8
    assert "REMOVEFILTERS ( 'Dataset' )" not in dax
    assert "ALL ( 'Regional KPI'" not in dax


def test_dax_has_transparent_relative_deltas_and_screening_cohort() -> None:
    dax = (ROOT / "powerbi/measures.dax").read_text(encoding="utf-8")
    for measure in [
        "Charging Points % vs Regional Median :=",
        "Fast Charging Points % vs Regional Median :=",
        "Charging Facilities % vs Regional Median :=",
        "Registered Nominal Power % vs Regional Median :=",
    ]:
        assert measure in dax
    assert "BEV Penetration vs Regional Median (pp) :=" in dax
    assert "Regions Above Total Median but Below Fast Median :=" in dax
    assert "Top 100 BEV Regions Below Both Medians :=" in dax
    assert "BEV Stock Rank :=" in dax
    assert "BEV Stock Rank Support :=" in dax
    assert "Screening Signal :=" in dax
    assert "Scatter Fast - Below Both :=" in dax
    assert "Investigation Attention Score :=" in dax


def test_report_spec_contains_two_visible_pages_and_no_stale_story() -> None:
    report = (ROOT / "powerbi/REPORT_SPEC.md").read_text(encoding="utf-8")
    for page in [
        "Page 1: Executive and Regional Screening",
        "Page 2: Region Profile",
    ]:
        assert page in report
    assert "Visible page count: **2**" in report
    assert "Page 3:" not in report
    assert "Page 4:" not in report
    assert "Regional Infrastructure Adequacy" not in report
    assert "Fast-Charging Coverage" not in report
    assert "No map" in report
    assert "53 of 100" in report
    assert "total-versus-fast regional provision scatter" in report.casefold()
    assert "regional median" in report.casefold()
    assert "National Median" not in report
    assert "composite investment score" in report


def test_report_spec_has_drillthrough_methodology_and_writing_contract() -> None:
    report = (ROOT / "powerbi/REPORT_SPEC.md").read_text(encoding="utf-8")
    standard = (ROOT / "docs/dashboard_design.md").read_text(
        encoding="utf-8"
    )
    assert "single-region slicer" in report.casefold()
    assert "`München, Stadt`" in report
    assert "publication-quality strip" in report
    assert "Power BI Service" in report
    assert "Dashboard writing standard" in standard
    assert "unlocking insights" in standard
    assert "Visible dashboard copy must also avoid" in standard
    assert "em dashes" in standard
    assert "Databricks AI/BI" in standard
    assert "Power BI" in standard


def test_analysis_summary_keeps_screening_scope_explicit() -> None:
    summary = load_json("evidence/analysis_summary.json")
    assert summary["governed_reporting_layer"] == (
        "Both dashboards use the same published Gold KPI layer."
    )
    assert "Screening evidence only" in summary["interpretation"]
    assert "does not make investment recommendations" in summary["interpretation"]


def test_theme_and_sql_request_files_are_valid_json() -> None:
    theme = load_json("powerbi/theme.json")
    assert theme["background"] == "#FFFFFF"
    assert theme["foreground"] == "#1F2937"
    assert theme["dataColors"][:3] == ["#1F9D8B", "#C65A7B", "#94A3B8"]
    defaults = theme["visualStyles"]["*"]["*"]
    assert defaults["border"][0]["show"] is True
    assert defaults["background"][0]["show"] is True
    for name in [
        "phase3_benchmarks_request.json",
        "phase3_screening_request.json",
        "phase3_validation_request.json",
        "phase3_pattern_summary_request.json",
        "phase3_quality_request.json",
    ]:
        request = load_json(f"databricks/sql/{name}")
        assert request["warehouse_id"] == "__WAREHOUSE_ID__"
        assert "__CATALOG__." in request["statement"]
        assert "vw_powerbi_" in request["statement"]
        assert "bronze." not in request["statement"].lower()
        assert "silver." not in request["statement"].lower()


def test_final_pbip_references_adjacent_report_and_semantic_model() -> None:
    project = load_json("powerbi/EV Charging Intelligence.pbip")
    assert project["artifacts"] == [
        {"report": {"path": "EV Charging Intelligence.Report"}}
    ]
    report_reference = load_json(
        "powerbi/EV Charging Intelligence.Report/definition.pbir"
    )
    assert report_reference["datasetReference"]["byPath"]["path"] == (
        "../EV Charging Intelligence.SemanticModel"
    )


def test_final_pbip_has_two_pages_and_seventy_four_measures() -> None:
    pages = load_json(
        "powerbi/EV Charging Intelligence.Report/definition/pages/pages.json"
    )
    assert len(pages["pageOrder"]) == 2
    tmdl = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(
            (ROOT / "powerbi/EV Charging Intelligence.SemanticModel/definition/tables").glob(
                "*.tmdl"
            )
        )
    )
    assert sum(line.lstrip().startswith("measure ") for line in tmdl.splitlines()) == 74


def test_final_pbip_is_public_safe_and_cache_free() -> None:
    root = ROOT / "powerbi"
    assert not list(root.rglob(".pbi"))
    assert not list(root.rglob("cache.abf"))
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".tmdl", ".md", ".pbip", ".pbir", ".pbism"}
    )
    assert ".cloud.databricks.com" not in combined
    assert not any(
        part.startswith("/sql/1.0/warehouses/") and "DATABRICKS_SQL_WAREHOUSE_ID" not in part
        for part in combined.split('"')
    )
    assert "DATABRICKS_SERVER_HOSTNAME" in combined
    assert "DATABRICKS_SQL_WAREHOUSE_ID" in combined
    assert "DATABRICKS_CATALOG" in combined
    windows_user_prefix = "C:" + "\\\\" + "Users" + "\\\\"
    assert windows_user_prefix not in combined


def test_power_bi_screenshots_have_one_canonical_public_location() -> None:
    assert not list((ROOT / "powerbi").rglob("*.png"))
    assert (ROOT / "dashboards/powerbi/executive-regional-screening.png").is_file()
    assert (ROOT / "dashboards/powerbi/region-profile.png").is_file()
