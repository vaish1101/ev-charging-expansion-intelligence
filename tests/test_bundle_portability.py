import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_creates_catalog_schemas_volume_and_workflow_lands_sources() -> None:
    bootstrap = (ROOT / "scripts/bootstrap_databricks.py").read_text()
    assert "CREATE CATALOG IF NOT EXISTS" in bootstrap
    assert '("landing", "bronze", "silver", "gold", "audit")' in bootstrap
    assert "CREATE VOLUME IF NOT EXISTS" in bootstrap

    workflow = yaml.safe_load((ROOT / "resources/workflow.yml").read_text())
    tasks = workflow["resources"]["jobs"]["ev_charging_pipeline"]["tasks"]
    assert tasks[0]["task_key"] == "immutable_source_landing"
    assert tasks[1]["depends_on"] == [{"task_key": "immutable_source_landing"}]


def test_runtime_notebooks_have_no_legacy_shared_paths_or_fixed_date_set() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "databricks/notebooks").glob("*.py"))
    )
    assert "/Workspace/Shared" not in text
    assert not any(part.startswith("ds_") and len(part) == 67 for part in text.split())
    assert 'CATALOG = "ev_analytics"' not in text


def test_bundle_syncs_checksum_bound_geography_evidence() -> None:
    bundle = yaml.safe_load((ROOT / "databricks.yml").read_text())
    includes = set(bundle["sync"]["include"])
    assert "data/reference/geography/geographic_reconciliation.csv" in includes
    assert "data/reference/geography/analysis_region_bridge.csv" in includes


def test_prepare_bundle_renders_catalog_and_keeps_template_portable(tmp_path: Path) -> None:
    env = os.environ.copy()
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prepare_bundle.py",
            "--catalog",
            "portable_catalog",
            "--output",
            str(tmp_path / "dashboard.lvdash.json"),
            "--skip-source-check",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout)["catalog"] == "portable_catalog"
    rendered = (tmp_path / "dashboard.lvdash.json").read_text()
    template = (
        ROOT / "databricks/dashboards/ev_charging_intelligence.template.lvdash.json"
    ).read_text()
    assert "portable_catalog.gold.vw_powerbi_region_kpi_published" in rendered
    assert "__CATALOG__" not in rendered
    assert "__CATALOG__.gold.vw_powerbi_region_kpi_published" in template
