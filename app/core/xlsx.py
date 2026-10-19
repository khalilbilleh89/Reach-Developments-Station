"""Bounded, non-executing workbook package checks shared by import adapters."""

import io
import zipfile

from app.core.errors import ValidationError

MAX_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED = 64 * 1024 * 1024
_READ_CHUNK = 256 * 1024


def check_archive(
    body: bytes, *, max_bytes: int = MAX_BYTES, max_uncompressed: int = MAX_UNCOMPRESSED
) -> None:
    """Refuse the package before anything inside it is decompressed.

    Order is the security property here, not the set of checks. An earlier
    version called ``ZipFile.testzip()`` first and compared the uncompressed
    size afterwards — and ``testzip`` decompresses every member to verify its
    CRC, so the bomb was expanded in order to decide whether it was too big to
    expand. The PR describing it claimed the opposite. It is now:

    1. the compressed bound, on bytes already in hand;
    2. the central directory, which is metadata and costs nothing;
    3. the declared uncompressed total, refused before any member is opened;
    4. macros and the shape of the package;
    5. only then, reading members — and never unboundedly.

    Step three is the gate that matters, and it is enough: ``ZipExtFile`` bounds
    each read by the declared ``file_size`` and then raises on the CRC
    mismatch, so an archive that understates itself truncates and fails rather
    than over-delivering — verified against CPython 3.11 rather than assumed.
    A bomb therefore has to declare its size to be readable at all, and the
    central directory is where it is refused.

    Step five replaces ``testzip`` rather than restoring it: the same CRC
    verification, but counted against the same bound as it goes, so nothing
    here can read more than the directory was judged on.
    """
    if not body:
        raise ValidationError("That file is empty.")
    if len(body) > max_bytes:
        raise ValidationError(
            f"That file is larger than the {max_bytes // (1024 * 1024)} MB limit for a workbook."
        )
    if body[:2] == b"\xd0\xcf":
        raise ValidationError(
            "That workbook is password-protected or in the older .xls format. Save it as "
            "an unprotected .xlsx and try again."
        )
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entries = archive.infolist()
            declared = sum(entry.file_size for entry in entries)
            if declared > max_uncompressed:
                raise ValidationError(
                    "That workbook expands to far more data than an import needs."
                )
            names = {entry.filename for entry in entries}
            if any(name.startswith("xl/vbaProject") for name in names):
                raise ValidationError(
                    "That workbook contains macros. Save it as a plain .xlsx — an "
                    "import reads data and never runs code."
                )
            if "xl/workbook.xml" not in names:
                raise ValidationError("That file is not a readable .xlsx workbook.")
            _read_within_bounds(archive, entries, max_uncompressed)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as caught:
        raise ValidationError(
            "That file is not a readable .xlsx workbook. Download the template and fill "
            "that in rather than converting another format."
        ) from caught


def _read_within_bounds(
    archive: zipfile.ZipFile, entries: list[zipfile.ZipInfo], max_uncompressed: int
) -> None:
    """Read every member through the uncompressed bound, verifying it on the way.

    The replacement for ``testzip``: same CRC verification, but the bytes are
    counted as they arrive, so an archive whose central directory understates
    what it holds is refused part-way through rather than after.
    """
    read = 0
    for entry in entries:
        with archive.open(entry) as member:
            while chunk := member.read(_READ_CHUNK):
                read += len(chunk)
                if read > max_uncompressed:
                    raise ValidationError(
                        "That workbook expands to far more data than an import needs."
                    )
