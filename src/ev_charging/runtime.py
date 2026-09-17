"""Runtime configuration shared by local tests and Databricks notebooks."""

from __future__ import annotations

import os
import re


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def catalog_name() -> str:
    """Return the configured Unity Catalog name after strict validation."""
    value = os.environ.get("EV_CATALOG", "ev_analytics")
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"EV_CATALOG must be a simple SQL identifier, observed {value!r}")
    return value


def volume_root() -> str:
    """Return the managed Volume root used for immutable source landing."""
    return os.environ.get(
        "EV_VOLUME_ROOT",
        f"/Volumes/{catalog_name()}/landing/raw_sources",
    ).rstrip("/")
