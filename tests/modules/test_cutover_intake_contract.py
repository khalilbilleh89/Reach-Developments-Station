"""Guards that keep the canonical intake contract honest against the schema.

The contract in ``docs/CANONICAL_INTAKE_CONTRACT.md`` decides, for every table in
this application, whether a legacy batch may write to it. A document like that
has one characteristic failure and it is not being wrong on the day it is
written: it is being right then and silently wrong six months later, when a
table lands and nobody classifies it. An unclassified table is a table somebody
may quietly start importing, and the first anybody hears of it is a migration
that wrote where nothing was meant to.

So the disposition is asserted to be a *partition* of the live schema — every
table classified, exactly once, and no table named that does not exist. A new
table fails this file until the change that adds it says which side of the line
it is on. That is the intended cost.

The second guard is smaller and comes from a real defect in this repository.
``ENGINEERING_RULES`` carried the sentence "``Backend Fast`` carries the same
two-hour ceiling" for a commit after the ceiling became four hours, because the
number was stated in one paragraph and repeated in another and only one was
edited. The contract cites database constraints by name — they are the reason
several of its rules exist — so every constraint name it cites is checked to
exist. A rule justified by a constraint that has been renamed away is a rule
nobody is enforcing.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
import subprocess
from pathlib import Path

import pytest

CONTRACT = Path("docs/CANONICAL_INTAKE_CONTRACT.md")

#: Asked of git from a fixed root rather than the working directory, so the
#: answer does not depend on where pytest was started.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Sections of the disposition, by the anchor that opens them. Together they must
#: account for the whole schema.
SECTIONS = ("PLATFORM", "DERIVED", "BUNDLE", "EXCLUDED")

_SECTION = re.compile(
    r"<!-- disposition:(?P<name>[A-Z]+) -->(?P<body>.*?)<!-- /disposition -->",
    re.DOTALL,
)
#: A disposition row: a table cell whose first content is one backticked name.
_ROW = re.compile(r"^\|\s*`(?P<table>[a-z_][a-z0-9_]*)`\s*\|", re.MULTILINE)
#: Constraint and index names follow the repository's own naming convention.
_CONSTRAINT = re.compile(r"`((?:ck|uq)_[a-z0-9_]+)`")


def schema_tables() -> frozenset[str]:
    """Every table the application actually declares."""
    import app.modules as modules

    for found in pkgutil.iter_modules(modules.__path__):
        try:
            importlib.import_module(f"app.modules.{found.name}.models")
        except ImportError:  # pragma: no cover - a module without models
            continue
    from app.db.base import Base

    return frozenset(Base.metadata.tables)


def schema_constraint_names() -> frozenset[str]:
    """Every named check constraint, unique constraint and index."""
    schema_tables()
    from app.db.base import Base

    names: set[str] = set()
    for table in Base.metadata.tables.values():
        names.update(str(c.name) for c in table.constraints if c.name)
        names.update(str(i.name) for i in table.indexes if i.name)
    return frozenset(names)


def import_order() -> list[str]:
    """The bundle files, in the order the contract says they are read.

    Module level rather than inline in one test because the fixture guards read
    it too: the synthetic bundle has to hold exactly these files, and two copies
    of this parsing would eventually disagree about which document is right.
    """
    text = CONTRACT.read_text(encoding="utf-8")
    block = re.search(r"```text\n(?P<body>[^`]*?\.csv[^`]*?)```", text, re.DOTALL)
    assert block is not None, "the import-order block is missing"
    return re.findall(r"^\s*\d+\s+([a-z_]+)\.csv", block.group("body"), re.MULTILINE)


def disposition() -> dict[str, list[str]]:
    """The document's classification, as ``{section: [table, ...]}``."""
    text = CONTRACT.read_text(encoding="utf-8")
    found = {m.group("name"): _ROW.findall(m.group("body")) for m in _SECTION.finditer(text)}
    assert set(found) == set(SECTIONS), f"unexpected disposition sections: {sorted(found)}"
    return found


# --------------------------------------------------------------------------- #
# The disposition is a partition of the schema
# --------------------------------------------------------------------------- #


def test_every_table_in_the_schema_is_classified() -> None:
    """A table nobody classified is a table nobody decided about.

    This is the guard that costs something, and it is meant to. Adding a table
    means saying, in the same change, whether a legacy batch may write to it.
    """
    classified = {t for rows in disposition().values() for t in rows}
    missing = sorted(schema_tables() - classified)
    assert not missing, (
        f"{len(missing)} table(s) have no disposition in {CONTRACT}: {missing}. "
        "Classify each as PLATFORM, DERIVED, BUNDLE or EXCLUDED."
    )


def test_the_contract_names_no_table_that_does_not_exist() -> None:
    """A rule about a table that was renamed away is a rule about nothing."""
    classified = {t for rows in disposition().values() for t in rows}
    phantom = sorted(classified - schema_tables())
    assert not phantom, f"{CONTRACT} classifies table(s) that do not exist: {phantom}"


def test_no_table_is_classified_in_two_sections() -> None:
    """Two dispositions for one table is one disposition too many.

    The case that matters is a table in both ``DERIVED`` and ``BUNDLE``: the
    document would simultaneously forbid and require importing it, and a reader
    would take whichever answer they found first. Repetition *within* one
    section is a different defect and has its own guard below.
    """
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for section, rows in disposition().items():
        for table in set(rows):
            if table in seen:
                clashes.append(f"{table}: {seen[table]} and {section}")
            else:
                seen[table] = section
    assert not clashes, f"tables classified in more than one section: {clashes}"


def test_a_section_does_not_list_the_same_table_twice() -> None:
    """Two rows for one table read as two rules; one of them will be stale."""
    for section, rows in disposition().items():
        duplicates = sorted({t for t in rows if rows.count(t) > 1})
        assert not duplicates, f"{section} lists {duplicates} more than once"


def test_the_partition_accounts_for_the_whole_schema() -> None:
    """Belt and braces: the counts have to add up, not just the sets."""
    rows = disposition()
    total = sum(len(v) for v in rows.values())
    assert total == len(schema_tables()), (
        f"{total} classified rows against {len(schema_tables())} tables — "
        "the disposition is not a partition"
    )


# --------------------------------------------------------------------------- #
# The rules cite constraints that exist
# --------------------------------------------------------------------------- #


def test_every_constraint_the_contract_cites_exists() -> None:
    """Several rules exist *because* of a named constraint. Names drift.

    ``ck_unit_area_schedules_approved_complete`` is why the contract says an
    approved area schedule needs an approver. If that constraint were renamed
    or dropped, the sentence would still read as a statement of fact about the
    database while being one about nothing.
    """
    cited = set(_CONSTRAINT.findall(CONTRACT.read_text(encoding="utf-8")))
    assert cited, "the contract cites no constraint at all — has it been rewritten?"
    unknown = sorted(cited - schema_constraint_names())
    assert not unknown, f"{CONTRACT} cites constraint(s) that do not exist: {unknown}"


# --------------------------------------------------------------------------- #
# The bundle is coherent
# --------------------------------------------------------------------------- #


def test_the_import_order_is_a_total_order_over_the_bundle() -> None:
    """Every file listed in the order block is a bundle table, and vice versa.

    A file in the order that is not in the bundle would be imported without a
    disposition. A bundle table missing from the order would have no defined
    point at which it is read, which for a single-transaction batch means its
    references may not exist yet.
    """
    ordered = import_order()
    assert ordered, "the import-order block lists no files"
    assert len(ordered) == len(set(ordered)), f"a file is listed twice: {ordered}"

    bundle = set(disposition()["BUNDLE"])
    assert set(ordered) <= bundle, (
        f"the import order lists non-bundle table(s): {sorted(set(ordered) - bundle)}"
    )


def test_the_unblocked_bundle_is_exactly_what_the_order_covers() -> None:
    """The order covers groups A and B; C and D are blocked and absent.

    This is the guard that stops the blocked half being quietly implemented. A
    blocked table appearing in the import order means somebody decided the B+
    seam or the source question was settled, and that decision should be visible
    in a diff rather than inferred from a sequence.
    """
    text = CONTRACT.read_text(encoding="utf-8")
    body = next(m.group("body") for m in _SECTION.finditer(text) if m.group("name") == "BUNDLE")
    groups = dict(re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*([A-D])\s*\|", body, re.MULTILINE))
    seen_groups = set(groups.values())
    assert seen_groups == {"A", "B", "C", "D"}, f"unexpected bundle groups: {sorted(seen_groups)}"

    ordered = set(import_order())
    unblocked = {t for t, g in groups.items() if g in {"A", "B"}}
    blocked = {t for t, g in groups.items() if g in {"C", "D"}}

    assert ordered == unblocked, (
        f"the import order does not match groups A+B; "
        f"missing {sorted(unblocked - ordered)}, extra {sorted(ordered - unblocked)}"
    )
    assert not (ordered & blocked), (
        f"blocked table(s) appear in the import order: {sorted(ordered & blocked)}"
    )


# --------------------------------------------------------------------------- #
# The prohibitions the contract turns on
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("sale_contracts", "reservation_id"),
        ("sale_contracts", "unit_price_version_id"),
        ("sale_contracts", "reservation_quote_snapshot_json"),
    ],
)
def test_the_native_provenance_pointers_are_still_mandatory(table: str, column: str) -> None:
    """Why groups C and D are blocked, asserted rather than asserted-in-prose.

    The contract says a legacy sale cannot land because these three are
    ``NOT NULL`` and a legacy sale has none of them. If the B+ seam later makes
    them conditionally nullable, this guard fails — and it should, because the
    paragraph explaining the block will need rewriting in the same change.
    """
    schema_tables()
    from app.db.base import Base

    assert not Base.metadata.tables[table].columns[column].nullable, (
        f"{table}.{column} is nullable now — the B+ seam has landed and the "
        f"contract's blocked-work section needs updating with it"
    )


# --------------------------------------------------------------------------- #
# The document and the code have to agree
# --------------------------------------------------------------------------- #

#: Target-side preflight checks that assert a thing *already exists*, paired
#: with the table each is about. A table named here may not also be in the
#: bundle: the check would refuse the batch that was about to create it.
PRE_EXISTING = {
    "project_known": "projects",
    "currencies_configured": "currencies",
}

_EMITTED_CHECK = re.compile(r'_check\(\s*\n?\s*"([a-z_]+)"')


def test_the_bundle_contains_nothing_the_preflight_requires_to_pre_exist() -> None:
    """The contradiction that shipped in the first draft of this contract.

    ``projects.csv`` was step one of the import order while ``resolve_project``
    refused an unknown code and ``project_known`` was a blocking preflight
    check — so the preflight of any first batch would have refused the very
    project the bundle was about to create. Both could not be right, and the
    guards above did not notice, because every one of them compares the document
    against itself.

    This compares it against the code. A check that asserts something already
    exists and a bundle file that creates that thing are a contradiction
    whichever of the two is wrong.
    """
    bundle = set(disposition()["BUNDLE"])
    clashes = sorted(
        f"{table} (asserted pre-existing by {check})"
        for check, table in PRE_EXISTING.items()
        if table in bundle
    )
    assert not clashes, f"the bundle creates what preflight requires to exist: {clashes}"


def test_every_pre_existing_table_is_classified_platform() -> None:
    """Not merely absent from the bundle — positively placed.

    A table dropped from the bundle and left unclassified would fail the
    partition guard; one classified DERIVED would say Reach computes it, which
    for a project or a currency is false. PLATFORM is the claim that matches
    the code: administered before any batch, resolved by it, never created.
    """
    platform = set(disposition()["PLATFORM"])
    misplaced = sorted(table for table in PRE_EXISTING.values() if table not in platform)
    assert not misplaced, f"asserted pre-existing but not classified PLATFORM: {misplaced}"


def test_the_named_checks_are_ones_the_preflight_actually_emits() -> None:
    """Keeps the map above honest as ``target.py`` changes.

    Read from the source rather than by running the checks, so this needs no
    database and no fixture: the point is whether the names still exist, and a
    renamed check would otherwise leave a rule here guarding nothing.
    """
    emitted = set(
        _EMITTED_CHECK.findall(
            (REPO_ROOT / "scripts/migration/target.py").read_text(encoding="utf-8")
        )
    )
    assert emitted, "no checks found in target.py — has it been rewritten?"
    unknown = sorted(set(PRE_EXISTING) - emitted)
    assert not unknown, f"PRE_EXISTING names check(s) target.py does not emit: {unknown}"


# --------------------------------------------------------------------------- #
# What may and may not be committed
# --------------------------------------------------------------------------- #


def ignored(path: str) -> bool:
    """Whether git would ignore ``path``, asked of git rather than of a regex.

    ``.gitignore`` precedence is not something to reimplement in a test: a later
    negation, a directory pattern, a leading slash all change the answer, and a
    test that got it subtly wrong would report a protection this repository does
    not have.
    """
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def test_the_cutover_working_directory_is_ignored() -> None:
    """Where the client's live commercial data sits while a batch is prepared."""
    assert ignored("migration-work/units.csv")
    assert ignored("migration-work/manifest.json")
    assert ignored("migration-work/evidence/preflight.json")


def test_a_source_workbook_is_ignored_wherever_it_is_dropped() -> None:
    """The realistic accident: a workbook in the root, swept up by ``git add -A``."""
    for path in ("Sales Data.xlsx", "extract.xls", "book.xlsm", "docs/whatever.xlsx"):
        assert ignored(path), path


def test_csv_is_not_ignored_because_the_fixture_has_to_be_committed() -> None:
    """The tightening that would look like an improvement and is not.

    The canonical bundle is CSV and the synthetic fixture is committed as CSV. A
    blanket ``*.csv`` rule would silently exclude the one form of this data that
    is supposed to be present, and the absence would be noticed late or never.
    Real bundles are kept out by *where* they live, not by their extension.

    Asked of git, and only of git. A first draft also asserted the literal
    ``*.csv`` was absent from the file, which failed immediately — the string is
    in the comment explaining why the rule is not there. That is the same shape
    as the guard in this repository that once searched for "force" and found the
    docstring promising there is no force flag. A behavioural check does not
    have that problem, and it is the behaviour that matters: a commented-out
    pattern ignores nothing.
    """
    assert not ignored("tests/fixtures/cutover/units.csv")
    assert not ignored("docs/example.csv")
    assert not ignored("migration-work-notes.csv"), "the rule is the directory, not a prefix"


def test_nothing_already_tracked_is_ignored() -> None:
    """A rule added for the cutover may not quietly shadow the repository.

    Checked against what git actually tracks rather than a sample: a pattern
    broad enough to hide an existing file is broad enough to hide the next one.
    """
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    shadowed = [path for path in tracked if ignored(path)]
    assert not shadowed, f"the ignore rules shadow tracked file(s): {shadowed[:10]}"
