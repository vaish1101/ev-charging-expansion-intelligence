import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "databricks/dashboards/ev_charging_intelligence.template.lvdash.json"
LABEL_AUDIT = ROOT / "evidence/geography_display_label_audit.json"
def load_dashboard() -> dict:
    return json.loads(DASHBOARD.read_text(encoding="utf-8"))


def test_dashboard_has_exactly_two_business_pages() -> None:
    dashboard = load_dashboard()
    assert [page["displayName"] for page in dashboard["pages"]] == [
        "Germany Market & Provision Screening",
        "Region Profile",
    ]
    assert all(page["pageType"] == "PAGE_TYPE_CANVAS" for page in dashboard["pages"])
    assert all(page["layoutVersion"] == "GRID_V1" for page in dashboard["pages"])


def test_published_dashboard_title_does_not_overstate_investment_support() -> None:
    resource = (ROOT / "resources/dashboard.yml").read_text(encoding="utf-8")
    evidence = json.loads(
        (ROOT / "evidence/dashboard_evidence.json").read_text(encoding="utf-8")
    )
    assert 'display_name: "EV Charging Expansion Intelligence"' in resource
    assert evidence["dashboard"]["display_name"] == "EV Charging Expansion Intelligence"
    assert "Investment" not in evidence["dashboard"]["display_name"]


def test_dashboard_queries_only_published_gold_views() -> None:
    dashboard = load_dashboard()
    assert {dataset["name"] for dataset in dashboard["datasets"]} == {
        "ds_region",
        "ds_national",
        "ds_profile_compare",
        "ds_profile_region",
        "ds_profile_compare_parameterized",
        "ds_quality",
    }
    combined = "\n".join(
        line for dataset in dashboard["datasets"] for line in dataset["queryLines"]
    ).casefold()
    assert "vw_powerbi_region_kpi_published" in combined
    assert "vw_powerbi_date_set_quality" in combined
    assert "bronze." not in combined
    assert "silver." not in combined
    assert "candidate_" not in combined
    assert "publication_state = 'published'" in combined
    assert "power_bi_refresh_ready = true" in combined


def test_dashboard_serving_views_are_fully_qualified() -> None:
    dashboard = load_dashboard()
    query_text = "\n".join(
        line for dataset in dashboard["datasets"] for line in dataset["queryLines"]
    )
    expected_references = {
        "__CATALOG__.gold.vw_powerbi_region_kpi_published": 6,
        "__CATALOG__.gold.vw_powerbi_date_set_quality": 6,
    }
    for qualified_name, expected_count in expected_references.items():
        assert query_text.count(qualified_name) == expected_count
    assert not re.search(
        r"(?<!__CATALOG__\.gold\.)vw_powerbi_(?:region_kpi_published|date_set_quality)",
        query_text,
    )


def test_dashboard_has_no_map_or_composite_score() -> None:
    text = DASHBOARD.read_text(encoding="utf-8").casefold()
    assert '"widgettype": "map"' not in text
    assert "composite score" not in text
    assert "opportunity score" not in text
    assert "opportunity score" not in text
    assert "investment_rank" not in text
    assert "priority score" not in text


def test_region_profile_defaults_to_munich_and_filters_both_profile_datasets() -> None:
    dashboard = load_dashboard()
    page = next(page for page in dashboard["pages"] if page["name"] == "region_profile")
    widget = next(
        item["widget"] for item in page["layout"] if item["widget"]["name"] == "profile_region_filter"
    )
    assert widget["spec"]["widgetType"] == "filter-single-select"
    assert widget["spec"]["selection"] == {
        "defaultSelection": {
            "values": {"dataType": "STRING", "values": [{"value": "München, Stadt"}]}
        }
    }
    assert widget["spec"]["disallowAll"] is True
    assert {query["query"]["datasetName"] for query in widget["queries"]} == {
        "ds_region",
        "ds_profile_region",
        "ds_profile_compare_parameterized",
    }
    parameter_bindings = {
        field["queryName"]
        for field in widget["spec"]["encodings"]["fields"]
        if field.get("parameterName") == "region_name"
    }
    assert parameter_bindings == {
        "profile_region_parameter",
        "profile_compare_parameter",
    }


def test_region_profile_uses_published_single_region_measures() -> None:
    dashboard = load_dashboard()
    datasets = {dataset["name"]: dataset for dataset in dashboard["datasets"]}
    for name in ("ds_profile_region", "ds_profile_compare_parameterized"):
        assert datasets[name]["parameters"][0]["keyword"] == "region_name"
        assert ":region_name" in "".join(datasets[name]["queryLines"])

    page = next(page for page in dashboard["pages"] if page["name"] == "region_profile")
    widgets = {item["widget"]["name"]: item["widget"] for item in page["layout"]}

    story_expression = widgets["profile_story"]["queries"][0]["query"]["fields"][0][
        "expression"
    ]
    assert story_expression == "MAX(`profile_story`)"

    comparison = widgets["profile_comparison_bars"]["queries"][0]["query"]
    assert comparison["disaggregated"] is True


def test_market_page_has_one_hero_scatter_and_no_competing_scatter() -> None:
    dashboard = load_dashboard()
    market = next(
        page for page in dashboard["pages"]
        if page["name"] == "germany_market_provision_screening"
    )
    types = [
        item["widget"].get("spec", {}).get("widgetType") for item in market["layout"]
    ]
    assert types.count("scatter") == 1
    assert "EV Market Scale vs Public Charging Provision" in DASHBOARD.read_text(
        encoding="utf-8"
    )
    assert "Total vs Fast Charging Provision" not in DASHBOARD.read_text(encoding="utf-8")


def test_infrastructure_details_are_compact_and_keep_nominal_power_semantics() -> None:
    dashboard = load_dashboard()
    profile = next(page for page in dashboard["pages"] if page["name"] == "region_profile")
    widget = next(
        item["widget"] for item in profile["layout"]
        if item["widget"]["name"] == "profile_infrastructure_details"
    )
    assert widget["spec"]["widgetType"] == "table"
    assert [column["fieldName"] for column in widget["spec"]["encodings"]["columns"]] == [
        "facilities",
        "normal_points",
        "fast_points",
        "nominal_power",
    ]
    nominal = widget["spec"]["encodings"]["columns"][-1]
    assert nominal["displayName"] == "Registered nominal power (kW)"
    assert "formatTemplate" not in nominal
    assert "nominal power" in nominal["displayName"].casefold()


def test_market_page_leads_with_three_scale_kpis_and_one_screening_signal() -> None:
    dashboard = load_dashboard()
    market = next(
        page for page in dashboard["pages"]
        if page["name"] == "germany_market_provision_screening"
    )
    widgets = {item["widget"]["name"]: item["widget"] for item in market["layout"]}
    expected = {
        "market_registered_bevs": "registered_bevs",
        "market_public_points": "in_service_points",
        "market_fast_points": "in_service_fast_points",
        "market_screening_signal": "high_bev_below_both",
    }
    assert all(widgets[name]["spec"]["widgetType"] == "counter" for name in expected)
    for name, field in expected.items():
        query_fields = widgets[name]["queries"][0]["query"]["fields"]
        assert [item["name"] for item in query_fields] == [field]
    assert not any(name.startswith("cohort_") for name in widgets)
    national_query = "".join(
        next(dataset for dataset in dashboard["datasets"] if dataset["name"] == "ds_national")[
            "queryLines"
        ]
    )
    assert "AS high_bev_below_both" in national_query
    assert "bev_rank <= 100" in national_query


def test_dashboard_uses_display_names_transparent_deltas_and_screening_language() -> None:
    text = DASHBOARD.read_text(encoding="utf-8")
    for phrase in [
        "analysis_region_display_name",
        "München, Stadt",
        "Düsseldorf, Stadt",
        "Rheinisch-Bergischer Kreis",
        "points_vs_median_percent",
        "fast_points_vs_median_percent",
        "Largest BEV Markets Below Both Medians",
        "Regions to Investigate",
        "Screening signal, not an investment ranking",
        "profile_story",
    ]:
        assert phrase in text
    assert "relatively underserved" not in text.casefold()
    assert "Infrastructure Adequacy" not in text
    assert "Fast-Charging Coverage" not in text


def test_business_dashboard_keeps_trust_compact_and_moves_engineering_detail_out() -> None:
    dashboard = load_dashboard()
    text = DASHBOARD.read_text(encoding="utf-8")
    profile = next(page for page in dashboard["pages"] if page["name"] == "region_profile")
    trust_item = next(
        item for item in profile["layout"]
        if item["widget"]["name"] == "profile_trust_strip"
    )
    trust = trust_item["widget"]
    assert trust_item["position"]["height"] == 2
    assert trust["spec"]["frame"] == {"showTitle": False}
    assert trust["spec"]["encodings"]["columns"] == [
        {"fieldName": "publication_summary", "displayName": "Published status"}
    ]
    for phrase in ["Published · ", "checks passed · ", "regions · KBA ", "-day lag", "Screening scope"]:
        assert phrase in text
    for removed in [
        "Data Quality & Definitions",
        "401 current Destatis districts",
        "Trier uses a governed 2-to-1 aggregation",
        "Controlled tests rejected invalid schema and checksum inputs",
        "Evidence Still Required",
    ]:
        assert removed not in text


def test_market_table_is_filtered_and_supports_native_drillthrough() -> None:
    dashboard = load_dashboard()
    market = next(
        page for page in dashboard["pages"]
        if page["name"] == "germany_market_provision_screening"
    )
    widget = next(
        item["widget"] for item in market["layout"]
        if item["widget"]["name"] == "market_regions_to_investigate"
    )
    query = widget["queries"][0]["query"]
    assert widget["spec"]["widgetType"] == "table"
    assert query["filters"] == [
        {"expression": "`bev_rank` <= 100 AND (`points_vs_median` < 0 OR `fast_points_vs_median` < 0)"}
    ]
    assert "Drill to > Region Profile" in widget["spec"]["frame"]["description"]


def test_region_profile_has_story_headlines_comparison_context_and_scope() -> None:
    dashboard = load_dashboard()
    profile = next(page for page in dashboard["pages"] if page["name"] == "region_profile")
    widgets = {item["widget"]["name"]: item["widget"] for item in profile["layout"]}
    region_query = "".join(
        next(
            dataset for dataset in dashboard["datasets"] if dataset["name"] == "ds_region"
        )["queryLines"]
    )
    assert "AS registered_bevs_rank_display" in region_query
    assert "BEV stock rank:" in region_query
    assert (
        widgets["profile_registered_bevs"]["spec"]["encodings"]["value"]["fieldName"]
        == "registered_bevs_rank_display"
    )
    assert widgets["profile_story"]["spec"]["widgetType"] == "counter"
    assert widgets["profile_comparison_bars"]["spec"]["widgetType"] == "bar"
    assert widgets["profile_comparison_bars"]["spec"]["mark"] == {"layout": "group"}
    assert widgets["profile_trust_strip"]["spec"]["widgetType"] == "table"
    assert "Screening scope" in "".join(
        widgets["profile_scope"]["multilineTextboxSpec"]["lines"]
    )


def test_all_region_display_labels_are_governed_unique_and_complete() -> None:
    audit = json.loads(LABEL_AUDIT.read_text(encoding="utf-8"))
    assert audit["analysis_region_rows"] == 400
    assert audit["label_rows"] == 400
    assert audit["unique_region_codes"] == 400
    assert audit["unique_display_labels"] == 400
    assert audit["null_or_blank_labels"] == 0
    assert audit["representative_labels"]["09162"] == "München, Stadt"
    assert audit["representative_labels"]["09184"] == "München, Landkreis"
    assert audit["representative_labels"]["05378"] == "Rheinisch-Bergischer Kreis"
    dashboard_text = DASHBOARD.read_text(encoding="utf-8")
    assert dashboard_text.count("display_labels(analysis_region_code, analysis_region_display_name)") == 4
    assert "INITCAP(REGEXP_REPLACE(analysis_region_name" not in dashboard_text


def test_market_scatter_focus_mix_delta_headers_and_freshness() -> None:
    dashboard = load_dashboard()
    market = next(
        page for page in dashboard["pages"]
        if page["name"] == "germany_market_provision_screening"
    )
    widgets = {item["widget"]["name"]: item["widget"] for item in market["layout"]}
    scatter = widgets["market_scale_provision_scatter"]
    assert scatter["spec"]["encodings"]["color"]["fieldName"] == "market_focus_group"
    assert scatter["spec"]["encodings"]["color"]["displayName"] == "Screening group"
    assert "fast_provision_group" not in DASHBOARD.read_text(encoding="utf-8")
    assert scatter["spec"]["frame"]["description"] == (
        "Regions farther right have larger BEV markets; regions lower on the chart have "
        "fewer public charging points per 1,000 BEVs."
    )
    mappings = scatter["spec"]["encodings"]["color"]["scale"]["mappings"]
    assert {item["value"]: item["color"] for item in mappings} == {
        "Top 100: fast below median": "#D94F8A",
        "Top 100: total below median": "#18B3AE",
        "Top 100: at/above both medians": "#38A8C7",
        "Other regions": "#7F969B",
    }
    assert widgets["market_point_mix"]["spec"]["mark"] == {"layout": "stack-100"}
    assert "154,702" in widgets["market_point_mix"]["spec"]["frame"]["description"]
    columns = widgets["market_regions_to_investigate"]["spec"]["encodings"]["columns"]
    assert [column["displayName"] for column in columns if "median_percent" in column["fieldName"]] == [
        "Δ Total %",
        "Δ Fast %",
    ]
    footer = "".join(widgets["market_footer"]["multilineTextboxSpec"]["lines"])
    assert "KBA Jul 2026" in footer
    assert "BNetzA Sep 2026" in footer
    assert "Destatis Jun 2026" in footer
    assert "62 days" in footer


def test_dashboard_visible_copy_follows_writing_and_theme_standard() -> None:
    dashboard = load_dashboard()
    visible_strings = []
    for page in dashboard["pages"]:
        visible_strings.append(page["displayName"])
        for item in page["layout"]:
            widget = item["widget"]
            visible_strings.extend(widget.get("multilineTextboxSpec", {}).get("lines", []))
            spec = widget.get("spec", {})
            frame = spec.get("frame", {})
            visible_strings.extend(
                value for value in [frame.get("title"), frame.get("description")] if value
            )
            encodings = spec.get("encodings", {})
            for encoding in encodings.values():
                candidates = encoding if isinstance(encoding, list) else [encoding]
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    if candidate.get("displayName"):
                        visible_strings.append(candidate["displayName"])
                    for nested in candidate.get("columns", []) + candidate.get("fields", []):
                        if nested.get("displayName"):
                            visible_strings.append(nested["displayName"])
    visible = "\n".join(visible_strings).casefold()
    assert "—" not in visible
    for banned in [
        "unlocking insights",
        "data-driven excellence",
        "empowering decision-making",
        "actionable intelligence",
        "strategic opportunities",
        "key takeaways",
        "deep dive",
        "comprehensive overview",
        "robust solution",
    ]:
        assert banned not in visible

    theme = dashboard["uiSettings"]["theme"]
    assert theme["canvasBackgroundColor"] == {"light": "#071A1F", "dark": "#071A1F"}
    assert theme["widgetBackgroundColor"] == {"light": "#0D242A", "dark": "#0D242A"}
    assert theme["fontColor"] == {"light": "#E8F1F2", "dark": "#E8F1F2"}
    assert theme["selectionColor"] == {"light": "#18B3AE", "dark": "#18B3AE"}
    assert theme["visualizationColors"] == ["#18B3AE", "#7F969B", "#D94F8A", "#38A8C7"]


def test_orchestrated_workflow_enforces_portable_dependency_chain() -> None:
    resource = yaml.safe_load(
        (ROOT / "resources/workflow.yml").read_text(encoding="utf-8")
    )
    workflow = resource["resources"]["jobs"]["ev_charging_pipeline"]
    assert workflow["name"] == "EV Analytics - Governed Publication Workflow"
    assert "email_notifications" not in workflow
    tasks = {task["task_key"]: task for task in workflow["tasks"]}
    assert list(tasks) == [
        "immutable_source_landing",
        "source_landing_validation",
        "bronze_ingestion",
        "silver_transformations",
        "gold_candidate_validate_publish",
        "serving_readiness",
    ]
    assert tasks["source_landing_validation"]["depends_on"] == [
        {"task_key": "immutable_source_landing"}
    ]
    assert tasks["bronze_ingestion"]["depends_on"] == [{"task_key": "source_landing_validation"}]
    assert tasks["silver_transformations"]["depends_on"] == [{"task_key": "bronze_ingestion"}]
    assert tasks["gold_candidate_validate_publish"]["depends_on"] == [
        {"task_key": "silver_transformations"}
    ]
    assert tasks["serving_readiness"]["depends_on"] == [
        {"task_key": "gold_candidate_validate_publish"}
    ]


def test_controlled_resilience_evidence_preserves_published_gold() -> None:
    evidence = json.loads(
        (ROOT / "evidence/resilience_evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["result"] == "PASS"
    assert evidence["schema_failure"]["result"] == "PASS"
    assert evidence["checksum_failure"]["result"] == "PASS"
    assert evidence["published_gold_preserved"] is True
    assert evidence["published_gold_before"] == evidence["published_gold_after"]
    assert evidence["valid_orchestrated_rerun"]["result"] == "SUCCESS"


def test_architecture_and_portfolio_assets_exist() -> None:
    for relative in [
        "assets/architecture/system_architecture.svg",
        "assets/demo/ev_charging_demo.mp4",
        "powerbi/README.md",
        "docs/methodology.md",
    ]:
        assert (ROOT / relative).is_file()


def test_no_pbix_was_fabricated() -> None:
    assert not list(ROOT.glob("**/*.pbix"))
