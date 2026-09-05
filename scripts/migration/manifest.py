"""The batch manifest: which exact files were reviewed, and proof they held still.

A cutover has one question underneath every other question — *are we applying
the same bytes somebody validated?* Validation reads the source, reports what it
found and what it refused, and a person then spends hours fixing rejects in the
source. The failure this module exists to prevent is the obvious one: the
operator fixes three rows, does not re-validate, and applies against a file the
report no longer describes.

So every source file is hashed at validation, the hashes travel in the manifest,
and ``apply`` recomputes them. A single changed byte refuses the apply and sends
the operator back through validation. That is the whole mechanism, and it is
deliberately not cleverer than that.

The manifest is also the top of the evidence chain. An auditor asking "what
produced this imported project?" follows:

    original source file + its hash
        → adapter version, once an adapter exists
    canonical intake file + its hash        ← this module
        → validation result
        → batch id
        → audit correlation id on every row written
        → reconciliation result

Nothing here is source-specific. A manifest describes files, not worksheets.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from scripts.migration import CONTRACT_VERSION

#: Read in blocks rather than whole: a source bundle is small, but a function
#: that loads an arbitrary operator-supplied file into memory is a habit worth
#: not forming.
_BLOCK = 1024 * 1024


class ManifestError(Exception):
    """The manifest is unusable, and saying why is the whole job."""


def hash_file(path: Path) -> str:
    """SHA-256 of one file, lowercase hex."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_BLOCK):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class SourceFile:
    """One canonical intake file and the hash it had when it was validated."""

    name: str
    sha256: str
    bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "sha256": self.sha256, "bytes": self.bytes}


@dataclass(frozen=True)
class Manifest:
    """What an operator declares before anything is read.

    Every field here is something a person must state deliberately. There are no
    defaults that guess: the cutover date in particular is required and is never
    derived from today, because a batch prepared on Friday and applied on Monday
    would otherwise silently change which day the opening cash position belongs
    to.
    """

    #: Stable for the life of the batch. The same id validated is the id
    #: applied, and it is what makes a second apply of the same batch findable.
    batch_id: uuid.UUID
    #: The project this batch belongs to, by its business code rather than a
    #: database id — a manifest is written by a person before the target is
    #: necessarily known to them.
    project_code: str
    #: Which system the extract came from, in the operator's own words.
    source_system: str
    #: When the extract was taken. Not when this manifest was written.
    extracted_at: datetime
    #: The business date the imported position is true as at. Explicit, always.
    cutover_date: date
    #: The currencies this batch is allowed to contain. A row in any other
    #: currency is a reject, not a conversion: there is no FX in this system and
    #: a cutover is not the place to invent one.
    expected_currencies: tuple[str, ...]
    #: The person accountable for this batch.
    operator: str
    #: Why this batch exists, for the audit record.
    reason: str
    #: The files, with the hashes they had at validation.
    files: tuple[SourceFile, ...] = ()
    #: The canonical intake contract these files were validated against.
    contract_version: str = CONTRACT_VERSION
    #: Free notes. Never source data.
    notes: str | None = None
    #: Set once an adapter exists; until then the operator produced the
    #: canonical bundle some other way and that is recorded as unknown rather
    #: than as a version that does not exist.
    adapter_version: str | None = None
    #: Populated only by ``verify_unchanged``; not part of the declaration.
    _verified: bool = field(default=False, compare=False, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_id": str(self.batch_id),
            "project_code": self.project_code,
            "source_system": self.source_system,
            "extracted_at": self.extracted_at.isoformat(),
            "cutover_date": self.cutover_date.isoformat(),
            "expected_currencies": list(self.expected_currencies),
            "operator": self.operator,
            "reason": self.reason,
            "contract_version": self.contract_version,
            "adapter_version": self.adapter_version,
            "notes": self.notes,
            "files": [source.as_dict() for source in self.files],
        }


_REQUIRED = (
    "batch_id",
    "project_code",
    "source_system",
    "extracted_at",
    "cutover_date",
    "expected_currencies",
    "operator",
    "reason",
)


def load(path: Path) -> Manifest:
    """Read a manifest an operator wrote. Refuses rather than filling in blanks.

    Every refusal names the field, because the operator is about to go and edit
    this file and "invalid manifest" would send them reading the whole thing.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ManifestError(f"No manifest at {path}.") from error
    except json.JSONDecodeError as error:
        raise ManifestError(f"The manifest at {path} is not valid JSON: {error}.") from error
    if not isinstance(raw, dict):
        raise ManifestError("A manifest is a JSON object.")

    missing = [name for name in _REQUIRED if raw.get(name) in (None, "", [])]
    if missing:
        raise ManifestError(
            "The manifest is missing " + ", ".join(missing) + ". Every one of these is a "
            "deliberate declaration and none of them has a safe default."
        )

    try:
        batch_id = uuid.UUID(str(raw["batch_id"]))
    except ValueError as error:
        raise ManifestError("batch_id must be a UUID.") from error

    try:
        extracted_at = datetime.fromisoformat(str(raw["extracted_at"]))
        cutover_date = date.fromisoformat(str(raw["cutover_date"]))
    except ValueError as error:
        raise ManifestError(
            "extracted_at must be an ISO 8601 timestamp and cutover_date an ISO 8601 "
            f"date: {error}."
        ) from error

    currencies = raw["expected_currencies"]
    if not isinstance(currencies, list) or not all(isinstance(code, str) for code in currencies):
        raise ManifestError("expected_currencies is a list of currency codes.")

    files = tuple(
        SourceFile(name=str(entry["name"]), sha256=str(entry["sha256"]), bytes=int(entry["bytes"]))
        for entry in raw.get("files", [])
        if isinstance(entry, dict) and {"name", "sha256", "bytes"} <= set(entry)
    )

    return Manifest(
        batch_id=batch_id,
        project_code=str(raw["project_code"]),
        source_system=str(raw["source_system"]),
        extracted_at=extracted_at,
        cutover_date=cutover_date,
        expected_currencies=tuple(str(code).upper() for code in currencies),
        operator=str(raw["operator"]),
        reason=str(raw["reason"]),
        files=files,
        contract_version=str(raw.get("contract_version", CONTRACT_VERSION)),
        notes=raw.get("notes"),
        adapter_version=raw.get("adapter_version"),
    )


def seal(manifest: Manifest, *, directory: Path, names: list[str]) -> Manifest:
    """Hash the bundle and return the manifest that describes it.

    Called by ``validate``. The returned manifest is what gets written beside
    the validation report, and it is what ``apply`` will be handed.
    """
    files: list[SourceFile] = []
    for name in sorted(names):
        source = directory / name
        if not source.is_file():
            raise ManifestError(f"The bundle is missing {name}.")
        files.append(SourceFile(name=name, sha256=hash_file(source), bytes=source.stat().st_size))
    return Manifest(
        batch_id=manifest.batch_id,
        project_code=manifest.project_code,
        source_system=manifest.source_system,
        extracted_at=manifest.extracted_at,
        cutover_date=manifest.cutover_date,
        expected_currencies=manifest.expected_currencies,
        operator=manifest.operator,
        reason=manifest.reason,
        files=tuple(files),
        contract_version=manifest.contract_version,
        notes=manifest.notes,
        adapter_version=manifest.adapter_version,
    )


def verify_unchanged(manifest: Manifest, *, directory: Path) -> None:
    """Refuse an apply whose source has moved since it was validated.

    The refusal is deliberately blunt and deliberately unfixable in place: there
    is no ``--force``, and there will not be one. The remedy is to validate
    again, which costs minutes and produces a report that describes the file
    actually about to be applied.
    """
    if not manifest.files:
        raise ManifestError(
            "This manifest carries no file hashes, so there is nothing to prove the source "
            "has not changed. Run validate first; apply reads the manifest validate wrote."
        )

    moved: list[str] = []
    for source_file in manifest.files:
        path = directory / source_file.name
        if not path.is_file():
            moved.append(f"{source_file.name} is gone")
            continue
        current = hash_file(path)
        if current != source_file.sha256:
            moved.append(
                f"{source_file.name} changed ({source_file.sha256[:12]}… → {current[:12]}…)"
            )

    if moved:
        raise ManifestError(
            "The source is not what was validated: "
            + "; ".join(moved)
            + ". Run validate again — the reject report and the totals in it describe the "
            "earlier files, and applying against these would apply something nobody reviewed."
        )
