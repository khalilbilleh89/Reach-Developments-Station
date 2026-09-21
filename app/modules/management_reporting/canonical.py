"""Deterministic integrity reference, not cryptographic non-repudiation."""

import hashlib
import json

from app.modules.management_reporting.schemas import SnapshotOut


def content_hash(snapshot: SnapshotOut) -> str:
    document = snapshot.model_dump(mode="json", exclude={"content_hash"})
    # Version-one snapshots before cancellation reporting have no such fact.
    # Optional read-model compatibility must not add a null to their historical
    # hash input; new captures explicitly contain a count, including zero.
    if snapshot.payload.overview.cancelled_sales is None:
        document["payload"]["overview"].pop("cancelled_sales", None)
    for project, captured in zip(
        snapshot.payload.projects, document["payload"]["projects"], strict=True
    ):
        if project.cancelled_sales is None:
            captured.pop("cancelled_sales", None)
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
