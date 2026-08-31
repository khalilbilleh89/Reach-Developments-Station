"""The register must not read the database once per plan.

The obvious way to build this screen is a loop: for each plan, ask for its
current version, then reconcile it, then read its instalments. That is about
five round trips per plan, and it reads every schedule twice — reconciling
loads the rows the caller then loads again. At the few hundred to few thousand
sales this roadmap plans for, drawing one list becomes thousands of queries.

So the register reads plans, then versions, then instalments, in three
statements, and does the grouping and the arithmetic in memory with the same
pure function the plan screen uses. These tests hold that shape: the number of
statements must not move when the number of plans does, and the totals must
still be right at fifty.

Counting is done with SQLAlchemy's own event hook. No profiler, no SQL
instrumentation package — a regression guard is not worth a dependency.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import event, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.modules.payment_plans.models import (
    PaymentPlan,
    PaymentPlanInstallment,
    PaymentPlanVersion,
)
from app.modules.sales.models import SaleContract
from tests.modules.conftest import plans_url

BULK_PLANS = 50
BULK_ROWS = 20


@contextmanager
def statements() -> Iterator[list[str]]:
    """Every SQL statement executed inside the block, in order."""
    seen: list[str] = []

    def record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        seen.append(statement)

    event.listen(Engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", record)


def _touching(seen: list[str], table: str) -> list[str]:
    return [statement for statement in seen if table in statement]


def _copy(row: object, **overrides: object) -> dict[str, object]:
    """The column values of a mapped row, minus the ones the database sets."""
    managed = {"id", "created_at", "updated_at"}
    values = {
        attribute.key: getattr(row, attribute.key)
        for attribute in inspect(type(row)).mapper.column_attrs
        if attribute.key not in managed
    }
    values.update(overrides)
    return values


def _bulk_plans(db: Session, sale_id: str, plan_id: str) -> None:
    """Fifty more plans, each with a version and twenty instalments.

    Written straight to the database rather than through the routes: fifty
    sales built the honest way would need a phase, unit, price, buyer and
    contract each, and this test is about how the register *reads*, not how
    plans are made. The rows are clones of ones the real path produced, so the
    shapes are genuine.

    The cloned contracts are marked completed, which keeps them out of the
    partial unique index that allows only one live contract per unit while
    leaving them fully visible to the register — which filters on nothing but
    the project and the caller's phase scope.
    """
    template_sale = db.get(SaleContract, uuid.UUID(sale_id))
    template_plan = db.get(PaymentPlan, uuid.UUID(plan_id))
    assert template_sale is not None and template_plan is not None
    template_version = db.scalars(
        select(PaymentPlanVersion).where(PaymentPlanVersion.payment_plan_id == template_plan.id)
    ).first()
    assert template_version is not None

    for index in range(BULK_PLANS):
        sale = SaleContract(
            **_copy(
                template_sale,
                sale_number=f"BULK-{index:03d}",
                spa_number=None,
                status="cancelled",
            )
        )
        db.add(sale)
        db.flush()
        plan = PaymentPlan(
            **_copy(
                template_plan,
                sale_contract_id=sale.id,
                plan_number=f"PLN-9{index:05d}",
            )
        )
        db.add(plan)
        db.flush()
        version = PaymentPlanVersion(
            **_copy(template_version, payment_plan_id=plan.id, version_number=1, status="active")
        )
        db.add(version)
        db.flush()
        share = Decimal("1") / BULK_ROWS
        principals = [
            (version.contract_value_covered * share).quantize(Decimal("0.01"))
            for _ in range(BULK_ROWS)
        ]
        principals[-1] += version.contract_value_covered - sum(principals)
        for sequence in range(1, BULK_ROWS + 1):
            db.add(
                PaymentPlanInstallment(
                    project_id=version.project_id,
                    payment_plan_version_id=version.id,
                    sequence=sequence,
                    label=f"Instalment {sequence}",
                    trigger_type="fixed_date",
                    contractual_due_date=template_version.effective_date,
                    actual_due_date=template_version.effective_date,
                    grace_days=0,
                    principal_amount=principals[sequence - 1],
                    principal_fraction=share.quantize(Decimal("0.000001")),
                    tax_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    trigger_status="scheduled",
                )
            )
    db.commit()


def test_the_register_reads_the_same_number_of_statements_at_any_size(
    db: Session,
    collections_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
    active_sale: str,
) -> None:
    """One plan and fifty-one plans cost the same number of queries."""
    plan_id, _version_id = active_plan
    with statements() as one_plan:
        assert collections_client.get(plans_url(project_id)).status_code == 200

    _bulk_plans(db, active_sale, plan_id)

    with statements() as many_plans:
        response = collections_client.get(plans_url(project_id))
    assert response.status_code == 200
    assert response.json()["total"] == BULK_PLANS + 1

    # The screen grew by fifty rows and a thousand instalments. The number of
    # round trips did not move at all.
    assert len(many_plans) == len(one_plan), (
        f"{len(one_plan)} statements for one plan, {len(many_plans)} for {BULK_PLANS + 1}"
    )
    assert len(_touching(many_plans, "payment_plan_installments")) == 1
    assert len(_touching(many_plans, "payment_plan_versions")) == 1


def test_the_register_totals_are_right_at_fifty_plans(
    db: Session,
    collections_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
    active_sale: str,
) -> None:
    """Reading in bulk must not change a single figure."""
    plan_id, _version_id = active_plan
    _bulk_plans(db, active_sale, plan_id)
    rows = collections_client.get(plans_url(project_id)).json()["rows"]
    assert len(rows) == BULK_PLANS + 1

    bulk = [row for row in rows if row["plan_number"].startswith("PLN-9")]
    assert len(bulk) == BULK_PLANS
    for row in bulk:
        assert row["installment_count"] == BULK_ROWS
        assert row["is_reconciled"] is True
        assert row["scheduled_principal_total"] == row["contract_value_covered"]
        assert row["version_status"] == "active"

    # And the plan built through the real routes still reads as it does on its
    # own screen.
    original = next(row for row in rows if row["plan_id"] == plan_id)
    detail = collections_client.get(f"{plans_url(project_id)}/{plan_id}").json()
    assert original["installment_count"] == detail["current"]["reconciliation"]["installment_count"]
    assert (
        original["scheduled_principal_total"]
        == detail["current"]["reconciliation"]["scheduled_principal_total"]
    )


def test_the_register_looks_forward_only_and_never_implies_collection(
    collections_client: TestClient,
    project_id: str,
    active_plan: tuple[str, str],
) -> None:
    """PR-MVP-06 cannot say whether a past instalment was paid.

    So the register offers the next date still to come and nothing else. An
    already-passed date surfaced as "next" would read as arrears, and there is
    no arrears in this module to read.
    """
    rows = collections_client.get(plans_url(project_id)).json()["rows"]
    row = next(row for row in rows if row["plan_id"] == active_plan[0])

    assert "next_scheduled_date" in row
    assert "next_forecast_date" in row
    for absent in (
        "paid_amount",
        "balance_due",
        "outstanding",
        "overdue",
        "days_overdue",
        "collected",
        "payment_status",
        "next_actual_due_date",
    ):
        assert absent not in row, f"{absent} has no business in a PR-MVP-06 register"
