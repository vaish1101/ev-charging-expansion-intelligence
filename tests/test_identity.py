import hashlib
import json

import pytest

from ev_charging.identity import canonical_json, date_set_id, source_revision_id


def test_manifest_hashing_is_canonical_and_deterministic():
    first = {"z": None, "a": "value"}
    second = {"a": "value", "z": None}
    expected_json = '{"a":"value","z":null}'
    expected_id = "ds_" + hashlib.sha256(expected_json.encode("utf-8")).hexdigest()

    assert canonical_json(first) == expected_json
    assert date_set_id(first) == (expected_id, expected_json)
    assert date_set_id(second) == (expected_id, expected_json)


def test_source_revision_identity_uses_full_digest():
    digest = "a" * 64
    assert source_revision_id("kba", "fz27_15", "2026-07-01", digest) == (
        f"kba:fz27_15:2026-07-01:{digest}"
    )


@pytest.mark.parametrize("digest", ["a" * 63, "A" * 64, "g" * 64])
def test_source_revision_rejects_noncanonical_digest(digest):
    with pytest.raises(ValueError):
        source_revision_id("kba", "fz27_15", "2026-07-01", digest)
