#!/usr/bin/env python3
"""Validate local source inputs and render catalog-specific Bundle assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "databricks/dashboards/ev_charging_intelligence.template.lvdash.json"
OUTPUT = ROOT / ".bundle_artifacts/ev_charging_intelligence.lvdash.json"
SOURCE_CONFIG = ROOT / "config/source_revisions_v1.json"
CATALOG = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sources() -> list[str]:
    config = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    validated = []
    for source in config["sources"]:
        if source["classification"] != "CORE_V1":
            continue
        path = ROOT / source["filename"]
        if not path.is_file():
            raise FileNotFoundError(
                f"Missing approved source {source['filename']}. Follow data/README.md before deployment."
            )
        if path.stat().st_size != source["size_bytes"] or sha256(path) != source["sha256"]:
            raise ValueError(f"Source bytes do not match the frozen contract: {source['filename']}")
        validated.append(source["filename"])
    if len(validated) != 3:
        raise ValueError(f"Expected three Core V1 sources, observed {len(validated)}")
    return validated


def render_dashboard(catalog: str, output: Path = OUTPUT) -> Path:
    if not CATALOG.fullmatch(catalog):
        raise ValueError("Catalog must be a simple Unity Catalog identifier")
    template = TEMPLATE.read_text(encoding="utf-8")
    if "__CATALOG__" not in template:
        raise ValueError("Dashboard template does not contain the catalog placeholder")
    rendered = template.replace("__CATALOG__", catalog)
    payload = json.loads(rendered)
    if "__CATALOG__" in json.dumps(payload):
        raise ValueError("Dashboard rendering left unresolved catalog placeholders")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="ev_analytics")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="Rendered dashboard path. Tests should use a temporary path.",
    )
    parser.add_argument(
        "--skip-source-check",
        action="store_true",
        help="Render the dashboard for CI without requiring uncommitted provider files.",
    )
    args = parser.parse_args()
    sources = [] if args.skip_source_check else validate_sources()
    output = render_dashboard(args.catalog, args.output)
    print(
        json.dumps(
            {
                "catalog": args.catalog,
                "dashboard": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output),
                "validated_sources": sources,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
