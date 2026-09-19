#!/usr/bin/env python3
"""Regenerate the public release manifest and checksum inventory."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "evidence/release"
MANIFEST = RELEASE_DIR / "FINAL_RELEASE_MANIFEST.md"
INVENTORY = RELEASE_DIR / "FILE_INVENTORY.sha256"
EXCLUDED_DIRS = {
    ".bundle_artifacts",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def public_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path != INVENTORY
        and not any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT).parts)
    )


def render_manifest() -> str:
    artifacts = [
        ("Root README", "README.md", "Business and technical project guide"),
        (
            "Databricks dashboard PDF",
            "dashboards/databricks/databricks-dashboard.pdf",
            "Final dashboard pages and successful workflow",
        ),
        (
            "Power BI dashboard PDF",
            "dashboards/powerbi/power-bi-dashboard.pdf",
            "Final two-page executive report",
        ),
        (
            "Power BI Project",
            "powerbi/EV Charging Intelligence.pbip",
            "Entry point for the version-controlled PBIP source",
        ),
        (
            "Databricks dashboard source",
            "databricks/dashboards/ev_charging_intelligence.template.lvdash.json",
            "Catalog-parameterized dashboard definition",
        ),
        (
            "Source manifest",
            "data/source_manifest.json",
            "Official source URLs, dates, sizes and checksums",
        ),
        (
            "Regional reference output",
            "data/reference/regional_kpi_snapshot.csv",
            "Portable 400-region Gold reference",
        ),
        (
            "Quality reference output",
            "data/reference/dataset_quality.csv",
            "Portable publication-quality reference",
        ),
        (
            "Clean deployment proof",
            "evidence/clean_deployment_proof.md",
            "Bundle, workflow and control evidence",
        ),
    ]
    rows = [
        "# Final Release Manifest",
        "",
        "This manifest identifies the principal public release artifacts. "
        "`FILE_INVENTORY.sha256` contains a checksum for every public file except the inventory itself.",
        "",
        "## Databricks workspace retirement",
        "",
        "The Databricks workspace was intentionally decommissioned after export and archival. "
        "Authenticated Bundle validation cannot be repeated against the deleted workspace. "
        "Reproducibility is supported by the source-controlled Bundle configuration, preserved clean deployment proof, reference outputs and automated tests.",
        "",
        "The complete Power BI PBIP source is included. Raw provider files are not redistributed.",
        "",
        "| Artifact | Path | SHA-256 | Visibility | Purpose |",
        "|---|---|---|---|---|",
    ]
    for name, relative, purpose in artifacts:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        rows.append(
            f"| {name} | `{relative}` | `{sha256(path)}` | Public | {purpose} |"
        )
    return "\n".join(rows) + "\n"


def main() -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(render_manifest(), encoding="utf-8")
    lines = [
        f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in public_files()
    ]
    INVENTORY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST.relative_to(ROOT)}")
    print(f"Wrote {INVENTORY.relative_to(ROOT)} with {len(lines)} entries")


if __name__ == "__main__":
    main()
