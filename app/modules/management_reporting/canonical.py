"""Deterministic integrity reference, not cryptographic non-repudiation."""

import hashlib
import json

from app.modules.management_reporting.schemas import SnapshotOut


def content_hash(snapshot: SnapshotOut) -> str:
    document = snapshot.model_dump(mode="json", exclude={"content_hash"})
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
