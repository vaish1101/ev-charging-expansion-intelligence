"""Immutable source-revision and date-set identities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, BinaryIO


def sha256_stream(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return sha256_stream(handle)


def source_revision_id(provider: str, dataset: str, reference_date: str, sha256: str) -> str:
    if len(sha256) != 64 or sha256.lower() != sha256:
        raise ValueError("sha256 must be a full lowercase hexadecimal digest")
    if any(character not in "0123456789abcdef" for character in sha256):
        raise ValueError("sha256 must be hexadecimal")
    return f"{provider}:{dataset}:{reference_date}:{sha256}"


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def date_set_id(manifest: dict[str, Any]) -> tuple[str, str]:
    encoded = canonical_json(manifest)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"ds_{digest}", encoded
