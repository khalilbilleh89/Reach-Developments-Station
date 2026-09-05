"""The orchestrator asks; it does not answer.

The temptation on cutover night is to write a reconciliation that compares
migrated totals against legacy ones. That is a second implementation of the
arithmetic — written in a hurry, against a source nobody has seen, by whoever is
awake — and when it disagrees with the first nobody can say which is wrong.

So the property under test is negative and structural: **this module performs no
arithmetic**, proved by walking its syntax tree, and every number it reports is
copied verbatim from the domain that computed it. The comparison below is
against the domains themselves rather than against a recorded expectation,
because a recorded expectation would be a third opinion.
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.projects.models import Project
from scripts.migration import reconcile

AS_OF = date(2026, 9, 30)
MODULE = Path(reconcile.__file__)


@pytest.fixture
def project(db: Session, project_id: str) -> Project:
    return db.scalars(select(Project).where(Project.id == project_id)).one()


# --------------------------------------------------------------------------- #
# It computes nothing
# --------------------------------------------------------------------------- #


#: The operators that would make this module a second implementation of the
#: arithmetic. ``BitOr`` is deliberately absent: ``Decimal | None`` in an
#: annotation is a ``BinOp`` too, and the first version of this guard forbade
#: every ``BinOp`` and failed on the module's own type hints. Naming the
#: operators that mean *computation* is the property; "no binary operator at
#: all" was a proxy for it that caught the wrong thing.
ARITHMETIC = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult)


def test_the_orchestrator_performs_no_arithmetic() -> None:
    """Read from the syntax tree, because a promise in a docstring is not one.

    An arithmetic operator anywhere in this module would be the second
    implementation arriving quietly — a subtraction that looked like tidying up
    and became an opinion about what a number should be. String building uses
    f-strings, which are ``JoinedStr``, so the rule costs nothing legitimate.
    """
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    found = [
        f"line {node.lineno}: {ast.unparse(node)}"
        for node in ast.walk(tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ARITHMETIC)
    ]
    assert not found, (
        f"{MODULE.name} computes: {found}. This module orchestrates "
        "reconciliations; the domains that own the numbers work them out."
    )


def test_it_reports_what_the_domains_said_and_nothing_else(db: Session, project: Project) -> None:
    """Compared against the domains, not against a number recorded here.

    A recorded expectation would be a third opinion about the same figures, and
    the day one of the domains changed its answer this test would fail for the
    wrong reason — or worse, keep passing while the orchestrator drifted.
    """
    from app.modules.cashflow import service as cashflow
    from app.modules.construction import service as construction

    findings = reconcile.run(db, project=project, as_of=AS_OF)

    from_construction = construction.reconciliation(db, project=project)
    from_cashflow = cashflow.reconciliation(db, project=project, as_of=AS_OF)
    assert len(findings) == len(from_construction) + len(from_cashflow) > 0

    for finding, check in zip(findings, [*from_construction, *from_cashflow], strict=True):
        if finding.source == "construction":
            assert finding.check == check.key
            assert finding.passed is check.ok
            assert finding.expected == check.expected
            assert finding.actual == check.amount
        else:
            assert finding.check == check.name
            assert finding.passed is check.passed
            assert finding.expected == check.expected
            assert finding.actual == check.actual


def test_each_adapter_carries_a_failing_check_through_unchanged(
    db: Session, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Written after a mutation that hardcoded ``passed=True`` passed everything.

    A bare project's one construction check happens to pass, so an adapter that
    ignored ``check.ok`` entirely was indistinguishable from one that read it —
    the fifth guard on this branch to be vacuous because the data never
    exercised both cases. Here each domain is made to return a failing check
    with distinct amounts, so every field has to be carried rather than guessed.
    """
    from app.modules.cashflow import calculator as cashflow_calc
    from app.modules.cashflow import service as cashflow
    from app.modules.construction import calculator as construction_calc
    from app.modules.construction import service as construction

    monkeypatch.setattr(
        construction,
        "reconciliation",
        lambda session, *, project: [
            construction_calc.Check(
                key="contract_lines:C-1",
                label="Contract C-1: lines against header",
                ok=False,
                amount=Decimal("99.00"),
                expected=Decimal("100.00"),
                detail=None,
            )
        ],
    )
    monkeypatch.setattr(
        cashflow,
        "reconciliation",
        lambda session, *, project, as_of: [
            cashflow_calc.Check(
                name="opening_total_splits",
                passed=False,
                expected=Decimal("250000.00"),
                actual=Decimal("249999.99"),
                detail="Opening cash does not split.",
            )
        ],
    )

    first, second = reconcile.run(db, project=project, as_of=AS_OF)

    # construction: key -> check, ok -> passed, amount -> actual, label as the
    # fallback detail because that shape has no detail of its own here.
    assert (first.source, first.check, first.passed) == (
        "construction",
        "contract_lines:C-1",
        False,
    )
    assert (first.expected, first.actual) == (Decimal("100.00"), Decimal("99.00"))
    assert first.detail == "Contract C-1: lines against header"

    # cashflow: name -> check, passed -> passed, actual -> actual.
    assert (second.source, second.check, second.passed) == (
        "cashflow",
        "opening_total_splits",
        False,
    )
    assert (second.expected, second.actual) == (Decimal("250000.00"), Decimal("249999.99"))
    assert second.detail == "Opening cash does not split."

    assert [f.check for f in reconcile.failed([first, second])] == [first.check, second.check]


def test_the_two_answer_shapes_are_adapted_rather_than_assumed_alike(
    db: Session, project: Project
) -> None:
    """``construction.Check`` and ``cashflow.Check`` genuinely disagree.

    One has ``key``/``ok``/``amount``; the other ``name``/``passed``/``actual``.
    A framework that assumed one shape would be inventing a convergence nobody
    built, and would read ``None`` off whichever fields it guessed wrong.
    """
    sources = {finding.source for finding in reconcile.run(db, project=project, as_of=AS_OF)}
    assert sources == {"construction", "cashflow"}, "both adapters produced findings"


# --------------------------------------------------------------------------- #
# One source failing does not end the report
# --------------------------------------------------------------------------- #


def test_a_source_that_raises_is_reported_and_the_others_still_run(
    db: Session, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither swallowed nor fatal.

    Letting one exception end the run would leave an operator knowing nothing
    about the domains that would have answered. Recording it as a pass would be
    the "check nobody made" failure this codebase keeps finding. It is a
    finding that did not pass, with the exception in its detail.
    """

    def explode(session: Session, project: Project, as_of: date) -> list[reconcile.Finding]:
        raise RuntimeError("the forecast is not readable")

    monkeypatch.setattr(
        reconcile,
        "SOURCES",
        (
            reconcile.Source(name="construction", ask=explode),
            reconcile.Source(name="cashflow", ask=reconcile.from_cashflow),
        ),
    )
    findings = reconcile.run(db, project=project, as_of=AS_OF)

    broken = [f for f in findings if f.source == "construction"]
    assert len(broken) == 1
    assert broken[0].passed is False
    assert broken[0].check == "reconciliation_ran"
    assert "the forecast is not readable" in broken[0].detail
    assert [f for f in findings if f.source == "cashflow"], "the other source still answered"


def test_failed_returns_only_what_did_not_pass() -> None:
    """The list an operator reads first."""
    findings = [
        reconcile.Finding("a", "one", True, None, None, ""),
        reconcile.Finding("b", "two", False, None, None, ""),
    ]
    assert [f.check for f in reconcile.failed(findings)] == ["two"]


# --------------------------------------------------------------------------- #
# What it is allowed to orchestrate
# --------------------------------------------------------------------------- #


def test_only_project_scoped_reconciliations_are_registered() -> None:
    """The version-scoped ones are absent on purpose, not by oversight.

    ``payment_plans`` and ``unit_economics`` reconcile a *version*. Which
    version is a decision, and a decision made here would be made by whoever
    wrote the orchestrator rather than by the domain that owns the numbers —
    the same mistake as computing the figures.
    """
    assert [source.name for source in reconcile.SOURCES] == ["construction", "cashflow"]
    text = MODULE.read_text(encoding="utf-8")
    assert "payment_plans" in text, "and the reason they are absent is written down"
    assert "unit_economics" in text


def test_money_survives_as_a_string_never_a_float() -> None:
    """``as_dict`` feeds an evidence artifact, and JSON numbers are floats."""
    rendered = reconcile.Finding(
        source="cashflow",
        check="opening_total",
        passed=False,
        expected=Decimal("250000.00"),
        actual=Decimal("249999.99"),
        detail="",
    ).as_dict()
    assert rendered["expected"] == "250000.00"
    assert rendered["actual"] == "249999.99"
    assert reconcile.Finding("s", "c", True, None, None, "").as_dict()["expected"] is None
