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
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from scripts.migration import CONTRACT_VERSION

#: Read in blocks rather than whole: a source bundle is small, but a function
#: that loads an arbitrary operator-supplied file into memory is a habit worth
#: not forming.
_BLOCK = 1024 * 1024

#: What a canonical intake file may be called. Deliberately narrow: the bundle
#: is a flat set of named files, so a name is a name and never a path. Anything
#: with a separator, a drive letter, a leading dot or a traversal segment is
#: refused before it is ever joined to a directory — a manifest is an
#: operator-supplied document, and joining an operator-supplied string to a
#: directory is how a hash of ``../../etc/passwd`` ends up in migration
#: evidence looking exactly like a hash of a source file.
_BUNDLE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.[A-Za-z0-9]+$")

#: Lowercase hex, the length SHA-256 actually produces.
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

#: Which canonical intake contracts this code can validate a batch against.
#: One entry today. When the contract changes, this set is where somebody
#: decides whether old sealed manifests may still be applied — a decision, not
#: a version-migration framework.
SUPPORTED_CONTRACT_VERSIONS = frozenset({CONTRACT_VERSION})


class ManifestError(Exception):
    """The manifest is unusable, and saying why is the whole job."""


def bundle_name(name: object, *, where: str) -> str:
    """The one place a bundle filename is proved to be a filename.

    Used by every path that turns a name into a path — parsing a manifest,
    sealing a bundle, verifying one before apply — because a check applied at
    two of those three is not a check.
    """
    if not isinstance(name, str):
        raise ManifestError(f"{where}: a file name must be a string, not {type(name).__name__}.")
    if not _BUNDLE_NAME.fullmatch(name):
        raise ManifestError(
            f"{where}: {name!r} is not a canonical intake file name. The bundle is a flat set "
            "of named files such as 'units.csv'; a name may not be a path, contain a separator "
            "or a drive letter, begin with a dot, or traverse out of the bundle."
        )
    return name


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
    #: The canonical intake contract this batch was validated against. Declared,
    #: never defaulted: a manifest sealed against an older contract must not be
    #: readable as though it had been sealed against today's, because the whole
    #: point of recording it is to answer "which rules was this proved under?"
    #: months later, when the answer is no longer obvious.
    contract_version: str
    #: The files, with the hashes they had at validation.
    files: tuple[SourceFile, ...] = ()
    #: Free notes. Never source data.
    notes: str | None = None
    #: Set once an adapter exists; until then the operator produced the
    #: canonical bundle some other way and that is recorded as unknown rather
    #: than as a version that does not exist.
    adapter_version: str | None = None

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
    "contract_version",
)


def _text(raw: dict[str, object], field: str) -> str:
    """One declared string, required to actually be one.

    ``str(value)`` would turn ``{"name": "x"}`` into ``"{'name': 'x'}"`` and
    record it as the operator. A manifest is evidence; a value that is not the
    type it claims to be is a malformed manifest, not a formatting problem.
    """
    value = raw.get(field)
    if not isinstance(value, str):
        raise ManifestError(f"{field} must be a string, not {type(value).__name__}.")
    text = value.strip()
    if not text:
        raise ManifestError(f"{field} must not be blank.")
    return text


def _currencies(raw: dict[str, object]) -> tuple[str, ...]:
    """The currencies this batch may contain.

    Normalised, never converted: there is no FX in this system and a cutover is
    not where one appears. A duplicate is refused rather than folded away,
    because two entries that differ only in case mean the operator was unsure
    what they were declaring.
    """
    value = raw.get("expected_currencies")
    if not isinstance(value, list) or not value:
        raise ManifestError("expected_currencies must be a non-empty list of currency codes.")
    codes: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise ManifestError("Every expected currency must be a non-blank string.")
        code = entry.strip().upper()
        if code in codes:
            raise ManifestError(f"expected_currencies lists {code} more than once.")
        codes.append(code)
    return tuple(codes)


def _files(raw: dict[str, object]) -> tuple[SourceFile, ...]:
    """The sealed hashes, parsed fail-closed.

    A manifest declaring ten files of which nine parse is not a nine-file
    manifest. It is a broken manifest, and quietly becoming the smaller one is
    the worst available outcome: apply would verify the nine it could read,
    report success, and write a batch nobody had proved.
    """
    value = raw.get("files", [])
    if not isinstance(value, list):
        raise ManifestError("files must be a list.")

    parsed: list[SourceFile] = []
    seen: set[str] = set()
    for index, entry in enumerate(value, start=1):
        where = f"files[{index}]"
        if not isinstance(entry, dict):
            raise ManifestError(f"{where}: every entry must be an object.")
        missing = sorted({"name", "sha256", "bytes"} - set(entry))
        if missing:
            raise ManifestError(f"{where}: missing {', '.join(missing)}.")

        name = bundle_name(entry["name"], where=where)
        if name in seen:
            raise ManifestError(f"{where}: {name} is listed more than once.")
        seen.add(name)

        digest = entry["sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ManifestError(f"{where}: sha256 must be 64 lowercase hex characters.")

        size = entry["bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ManifestError(f"{where}: bytes must be a non-negative whole number.")

        parsed.append(SourceFile(name=name, sha256=digest, bytes=size))
    return tuple(parsed)


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
        batch_id = uuid.UUID(_text(raw, "batch_id"))
    except ValueError as error:
        raise ManifestError("batch_id must be a UUID.") from error

    try:
        extracted_at = datetime.fromisoformat(_text(raw, "extracted_at"))
    except ValueError as error:
        raise ManifestError(f"extracted_at must be an ISO 8601 timestamp: {error}.") from error
    if extracted_at.tzinfo is None:
        raise ManifestError(
            "extracted_at must carry a timezone offset. It is the moment the source was taken "
            "and it is read by people in other places; a naive timestamp is a different claim "
            "depending on who reads it."
        )

    try:
        cutover_date = date.fromisoformat(_text(raw, "cutover_date"))
    except ValueError as error:
        raise ManifestError(f"cutover_date must be an ISO 8601 date: {error}.") from error

    contract_version = _text(raw, "contract_version")
    if contract_version not in SUPPORTED_CONTRACT_VERSIONS:
        raise ManifestError(
            f"This manifest was validated against canonical intake contract {contract_version!r}, "
            f"which this code cannot apply. Supported: "
            f"{', '.join(sorted(SUPPORTED_CONTRACT_VERSIONS))}. Validate the batch again under "
            "the current contract rather than applying it under rules it was never proved against."
        )

    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise ManifestError("notes must be a string when present.")
    adapter_version = raw.get("adapter_version")
    if adapter_version is not None and not isinstance(adapter_version, str):
        raise ManifestError("adapter_version must be a string when present.")

    return Manifest(
        batch_id=batch_id,
        project_code=_text(raw, "project_code"),
        source_system=_text(raw, "source_system"),
        extracted_at=extracted_at,
        cutover_date=cutover_date,
        expected_currencies=_currencies(raw),
        operator=_text(raw, "operator"),
        reason=_text(raw, "reason"),
        contract_version=contract_version,
        files=_files(raw),
        notes=notes,
        adapter_version=adapter_version,
    )


def seal(manifest: Manifest, *, directory: Path, names: list[str]) -> Manifest:
    """Hash the bundle and return the manifest that describes it.

    Called by ``validate``. The returned manifest is what gets written beside
    the validation report, and it is what ``apply`` will be handed.
    """
    # Proved before anything is hashed, so the invariant holds where the manifest
    # is made rather than where it is next read. Serialising and re-loading would
    # catch a duplicate, but a Manifest that is wrong in memory is wrong now —
    # and the caller between here and there is the one that would apply it.
    canonical: list[str] = []
    for raw_name in names:
        name = bundle_name(raw_name, where="bundle")
        if name in canonical:
            raise ManifestError(f"The bundle lists {name} more than once.")
        canonical.append(name)

    files: list[SourceFile] = []
    for name in sorted(canonical):
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
        path = directory / bundle_name(source_file.name, where="manifest")
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
