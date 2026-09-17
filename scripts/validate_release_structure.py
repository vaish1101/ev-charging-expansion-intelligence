"""Validate the portable public artifacts that are not exercised by unit tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]


def validate_serialized_files() -> None:
    json_suffixes = {".json", ".pbip", ".pbir", ".pbism"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in json_suffixes:
            json.loads(path.read_text(encoding="utf-8-sig"))
        elif path.suffix.lower() in {".yml", ".yaml"}:
            yaml.safe_load(path.read_text(encoding="utf-8"))


def validate_power_bi() -> None:
    project = json.loads(
        (ROOT / "powerbi/EV Charging Intelligence.pbip").read_text(encoding="utf-8-sig")
    )
    report_path = ROOT / "powerbi" / project["artifacts"][0]["report"]["path"]
    report = json.loads((report_path / "definition.pbir").read_text(encoding="utf-8-sig"))
    semantic_path = (report_path / report["datasetReference"]["byPath"]["path"]).resolve()
    assert semantic_path.is_dir()
    pages = json.loads(
        (report_path / "definition/pages/pages.json").read_text(encoding="utf-8-sig")
    )
    assert len(pages["pageOrder"]) == 2
    measures = sum(
        line.lstrip().startswith("measure ")
        for path in (semantic_path / "definition/tables").glob("*.tmdl")
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    assert measures == 74


def validate_media() -> None:
    pdf_pages = {
        "dashboards/databricks/databricks-dashboard.pdf": 3,
        "dashboards/powerbi/power-bi-dashboard.pdf": 2,
    }
    for relative, expected in pdf_pages.items():
        reader = PdfReader(ROOT / relative)
        assert len(reader.pages) == expected
        assert all(float(page.mediabox.width) > 0 and float(page.mediabox.height) > 0 for page in reader.pages)

    video = (ROOT / "assets/demo/ev_charging_demo.mp4").read_bytes()[:32]
    assert b"ftyp" in video
    thumbnail = ROOT / "assets/demo/ev_charging_demo_thumbnail.png"
    assert thumbnail.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def validate_mermaid() -> None:
    blocks = []
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        blocks.extend(re.findall(r"```mermaid\s*\n(.*?)```", text, flags=re.DOTALL))
    assert len(blocks) == 2
    for block in blocks:
        assert block.lstrip().startswith("flowchart ")
        assert "-->" in block
        assert block.count("[") == block.count("]")
        assert block.count("{") == block.count("}")


def validate_public_tree() -> None:
    forbidden_names = {
        ".DS_Store",
        ".env",
        ".databrickscfg",
        "cache.abf",
        "localSettings.json",
        "editorSettings.json",
    }
    forbidden_suffixes = {".pbix", ".pbit", ".mov", ".csv", ".xlsx"}
    allowed_data = (ROOT / "data/reference").resolve()
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        assert path.name not in forbidden_names
        if path.suffix.lower() in forbidden_suffixes:
            assert allowed_data in path.resolve().parents


def main() -> None:
    validate_serialized_files()
    validate_power_bi()
    validate_media()
    validate_mermaid()
    validate_public_tree()
    print("Release structure validation passed")


if __name__ == "__main__":
    main()
