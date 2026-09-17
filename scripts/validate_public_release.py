#!/usr/bin/env python3
"""Fail when the public candidate contains broken links or private runtime metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
WORKSPACE_HOST = re.compile(
    r"https?://(?!docs\.databricks\.com)[^\s)\]>'\"]*\.databricks\.com",
    re.IGNORECASE,
)
CREDENTIAL = re.compile(
    r"dapi[a-z0-9]{20,}|client_secret\s*[:=]|access_token\s*[:=]|refresh_token\s*[:=]",
    re.IGNORECASE,
)
WINDOWS_LOCAL_PATH = re.compile(
    r"(?:[A-Z]:[\\/](?:Users|Documents and Settings|ProgramData|Windows)[\\/]|"
    r"\\\\Users\\\\|AppData[\\/])",
    re.IGNORECASE,
)
PRIVATE_EVIDENCE_KEY = re.compile(
    r"(?:^|_)(?:statement|task|parent|workflow|job|run|gold_run|silver_run|ingestion_run|"
    r"dashboard|warehouse|workspace|organization|account)(?:_page)?_(?:id|url)$",
    re.IGNORECASE,
)


def local_link_errors() -> list[str]:
    errors = []
    for document in sorted(ROOT.rglob("*.md")):
        if any(part in {".git", ".databricks", ".bundle_artifacts"} for part in document.parts):
            continue
        for raw in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            target = raw.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if path_text and not (document.parent / path_text).resolve().exists():
                errors.append(f"{document.relative_to(ROOT)} -> {target}")
    return errors


def evidence_key_errors() -> list[str]:
    errors = []

    def walk(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if PRIVATE_EVIDENCE_KEY.search(key):
                    errors.append(f"{path}: {key}")
                walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    for directory in (ROOT / "evidence", ROOT / "reports"):
        if not directory.exists():
            continue
        for report in sorted(directory.rglob("*.json")):
            walk(json.loads(report.read_text(encoding="utf-8")), str(report.relative_to(ROOT)))
    return errors


def text_errors() -> list[str]:
    errors = []
    extensions = {
        ".md", ".json", ".yml", ".yaml", ".py", ".sql", ".dax", ".m",
        ".tmdl", ".pbip", ".pbir", ".pbism",
    }
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or (
            path.suffix.lower() not in extensions and path.name != ".platform"
        ):
            continue
        if any(
            part in {
                ".git",
                ".databricks",
                ".bundle_artifacts",
                ".private_archive",
                ".private_capture",
                "EV_Charging_GitHub_Release",
            }
            for part in path.parts
        ):
            continue
        if "data" in path.parts and "raw" in path.parts:
            continue
        if path == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if WORKSPACE_HOST.search(text):
            errors.append(f"workspace host in {path.relative_to(ROOT)}")
        if CREDENTIAL.search(text):
            errors.append(f"credential pattern in {path.relative_to(ROOT)}")
        if WINDOWS_LOCAL_PATH.search(text):
            errors.append(f"local Windows path in {path.relative_to(ROOT)}")
        lowered = text.casefold()
        for placeholder in (
            "link" + " pending",
            "coming" + " soon",
            "<repo" + "-url>",
            "<this-repository" + "-url>",
        ):
            if placeholder in lowered:
                errors.append(f"placeholder '{placeholder}' in {path.relative_to(ROOT)}")
    return errors


def temporary_power_bi_errors() -> list[str]:
    errors = []
    powerbi = ROOT / "powerbi"
    if not powerbi.exists():
        return errors
    for path in powerbi.rglob("*"):
        if path.name == ".pbi" or path.name in {
            "cache.abf", "localSettings.json", "editorSettings.json"
        }:
            errors.append(f"temporary Power BI state in {path.relative_to(ROOT)}")
    return errors


def main() -> None:
    errors = (
        local_link_errors()
        + evidence_key_errors()
        + text_errors()
        + temporary_power_bi_errors()
    )
    if errors:
        raise SystemExit("Public release validation failed:\n" + "\n".join(f"- {item}" for item in errors))
    print("Public release validation passed")


if __name__ == "__main__":
    main()
