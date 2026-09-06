"""Runs the reconciliations this application already has. Computes nothing.

The temptation, on cutover night, is to write a reconciliation that compares the
migrated totals against the legacy ones. That would be a second implementation
of the arithmetic — a second opinion about what the number should be — and when
the two disagree nobody could say which was wrong. Worse, it would be an
implementation written in a hurry, against a source nobody has seen, by whoever
was awake.

So this module is an **orchestrator and nothing else**. Reach already knows how
to ask whether a contract's lines agree with its header, whether a forecast's
opening cash splits into its two components, whether the construction version a
cashflow pins is still the current one. Those questions are asked by the
domains that own the numbers, and they are the only questions asked here. This
file runs them, normalises two genuinely different answer shapes into one, and
reports.

**It performs no arithmetic**, and that is asserted rather than promised:
``test_cutover_reconcile.py`` walks this module's syntax tree and fails on any
binary operator. An orchestrator that started subtracting would be the second
implementation, arriving quietly.

The two answer shapes are different and are not pretended otherwise.
``construction.calculator.Check`` has ``key``/``label``/``ok``/``amount``;
``cashflow.calculator.Check`` has ``name``/``passed``/``actual``. Each gets its
own adapter, named as such, because a framework that assumed one shape would be
inventing a convergence nobody built.

**Every expected value in a real reconciliation is source-derived**, and the
source does not exist. Nothing here knows what the numbers ought to be after a
migration — it knows how to ask the application, and it will ask the same
questions before and after a batch so the difference is the finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable
    from datetime import date
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from app.modules.projects.models import Project


@dataclass(frozen=True)
class Finding:
    """One answer, from one domain, in one shape.

    ``expected`` and ``actual`` are copied verbatim from the domain that
    computed them. Nothing here derives, rounds or compares them: the domain
    already decided whether its own check passed, and re-deciding would be the
    second opinion this module exists to avoid.
    """

    source: str
    check: str
    passed: bool
    expected: Decimal | None
    actual: Decimal | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "check": self.check,
            "passed": self.passed,
            "expected": None if self.expected is None else str(self.expected),
            "actual": None if self.actual is None else str(self.actual),
            "detail": self.detail,
        }


def from_construction(session: Session, project: Project, as_of: date) -> list[Finding]:
    """Adapter for ``construction.service.reconciliation``.

    ``as_of`` is accepted and unused: construction reconciles against the rows
    as they stand, and a signature that varied by domain would push the choice
    of which argument to pass into the orchestrator, where it would be guessed.
    """
    from app.modules.construction import service

    del as_of
    return [
        Finding(
            source="construction",
            check=check.key,
            passed=check.ok,
            expected=check.expected,
            actual=check.amount,
            detail=check.detail or check.label,
        )
        for check in service.reconciliation(session, project=project)
    ]


def from_cashflow(session: Session, project: Project, as_of: date) -> list[Finding]:
    """Adapter for ``cashflow.service.reconciliation``."""
    from app.modules.cashflow import service

    return [
        Finding(
            source="cashflow",
            check=check.name,
            passed=check.passed,
            expected=check.expected,
            actual=check.actual,
            detail=check.detail,
        )
        for check in service.reconciliation(session, project=project, as_of=as_of)
    ]


@dataclass(frozen=True)
class Source:
    """One domain that can answer for itself."""

    name: str
    ask: Callable[[Session, Project, date], list[Finding]]


#: Every reconciliation this orchestrator runs. Project-scoped only, because
#: those are the ones that need no choice made for them. ``payment_plans`` and
#: ``unit_economics`` reconcile a *version* — which version is a decision, and a
#: decision made here would be made by whoever wrote this file rather than by
#: the domain that owns the numbers. They are absent for that reason and not
#: because they were overlooked.
SOURCES: tuple[Source, ...] = (
    Source(name="construction", ask=from_construction),
    Source(name="cashflow", ask=from_cashflow),
)


def run(session: Session, *, project: Project, as_of: date) -> list[Finding]:
    """Ask every source, and report what each said.

    A source that raises is reported as a finding that did not pass, with the
    exception in its detail, and the remaining sources still run. Letting one
    failure end the report would leave an operator knowing nothing about the
    domains that would have answered; recording it as a pass would be the
    "check nobody made" failure this codebase keeps finding. It is neither.
    """
    findings: list[Finding] = []
    for source in SOURCES:
        try:
            findings.extend(source.ask(session, project, as_of))
        except Exception as error:  # reported as a finding, never swallowed
            findings.append(
                Finding(
                    source=source.name,
                    check="reconciliation_ran",
                    passed=False,
                    expected=None,
                    actual=None,
                    detail=f"{type(error).__name__}: {error}",
                )
            )
    return findings


def failed(findings: list[Finding]) -> list[Finding]:
    """The ones that did not pass. The list an operator reads first."""
    return [finding for finding in findings if not finding.passed]
