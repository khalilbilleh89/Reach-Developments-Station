"""Direct API callers must supply a reason before changing governed cash."""

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent
from app.modules.cashflow.schemas import PreLaunchExpenseRemove, ReasonRequest
from tests.modules.conftest import cashflow_url, record_development, record_financing

BLANK_REASONS = ("", " ", "\t\r\n", "\u00a0\u2003\u202f")


def test_reason_contract_rejects_blank_text_without_rewriting_valid_reasons() -> None:
    expected = {
        "category": "consultants",
        "amount": "100.00",
        "movement_date": "2026-09-12",
        "counterparty_reference": None,
        "invoice_reference": None,
        "evidence_reference": None,
        "notes": None,
    }
    for schema, extra in ((ReasonRequest, {}), (PreLaunchExpenseRemove, {"expected": expected})):
        for reason in BLANK_REASONS:
            with pytest.raises(ValidationError) as caught:
                schema.model_validate({"reason": reason, **extra})
            assert caught.value.errors()[0]["loc"] == ("reason",)
        for reason in ("x", "  Duplicate entry  ", "تصحيح القيد", "x" * 1000):
            assert schema.model_validate({"reason": reason, **extra}).reason == reason
        with pytest.raises(ValidationError):
            schema.model_validate({"reason": "x" * 1001, **extra})


@pytest.mark.parametrize("kind", ["development", "financing"])
@pytest.mark.parametrize("confirmed", [False, True])
def test_blank_reversal_leaves_cash_and_audit_unchanged_then_valid_reason_succeeds(
    kind: str,
    confirmed: bool,
    finance_client: TestClient,
    second_finance_client: TestClient,
    project_id: str,
    currency_id: str,
    db: Session,
) -> None:
    record = record_development if kind == "development" else record_financing
    created = record(finance_client, project_id, currency_id)
    assert created.status_code == 201, created.text
    movement_id = created.json()["id"]
    register = f"{cashflow_url(project_id)}/{kind}-movements"
    if confirmed:
        response = second_finance_client.post(f"{register}/{movement_id}/confirm", json={})
        assert response.status_code == 200, response.text

    def movement() -> dict:
        response = finance_client.get(register)
        assert response.status_code == 200, response.text
        return next(row for row in response.json() if row["id"] == movement_id)

    before = movement()
    assert before["counts_as_cash"] is confirmed
    event_query = select(AuditEvent).where(
        AuditEvent.entity_id == uuid.UUID(movement_id),
        AuditEvent.action == f"cashflow.{kind}_movement_reversed",
    )
    for reason in BLANK_REASONS:
        refused = finance_client.post(f"{register}/{movement_id}/reverse", json={"reason": reason})
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"][0]["loc"] == ["body", "reason"]
        assert movement() == before
        assert db.scalars(event_query).all() == []

    reason = "  Duplicate transfer reference  "
    removed = finance_client.post(f"{register}/{movement_id}/reverse", json={"reason": reason})
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "reversed"
    assert removed.json()["counts_as_cash"] is False
    events = db.scalars(event_query).all()
    assert len(events) == 1
    assert events[0].reason == reason
    assert events[0].actor_user_id is not None
    assert events[0].before_data["status"] == before["status"]
    assert events[0].after_data["status"] == "reversed"
