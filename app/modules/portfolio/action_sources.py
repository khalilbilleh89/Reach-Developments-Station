"""API composition validates minimal source provenance against authorized truth."""

from datetime import date, timedelta

from sqlalchemy import Select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.portfolio import risk_projection
from app.modules.portfolio.outlook_sources import observations


def current_source(
    session: Session,
    scope: Select,
    as_of: date,
    source_type: str,
    code: str | None,
    key: str | None,
) -> dict | None:
    if source_type == "portfolio_risk":
        evaluations = []
        page = risk_projection.page(
            session, scope, as_of, limit=1, offset=0, source_key=key, evaluations=evaluations
        )
        if page.items and page.items[0].risk_code == code:
            row = page.items[0]
            return {"state": "current", "title": row.title, "drilldown": row.drilldown}
        if any(row.risk_code == code and row.availability == "available" for row in evaluations):
            return {
                "state": "resolved",
                "title": "Source condition resolved. The action workflow remains independent.",
                "drilldown": None,
            }
    elif source_type == "portfolio_outlook":
        for row in observations(session, scope, as_of, as_of + timedelta(days=90), [], []):
            if (
                row.source_key == key
                and row.item_type == code
                and row.availability != "unavailable"
            ):
                return {"state": "current", "title": row.title, "drilldown": row.drilldown}
    return None


def validate(
    session: Session,
    scope: Select,
    as_of: date,
    source_type: str,
    code: str | None,
    key: str | None,
    observed: date | None,
) -> None:
    if source_type == "manual":
        if any(value is not None for value in (code, key, observed)):
            raise ValidationError("Manual actions cannot carry source provenance.")
        return
    if not code or not key or observed != as_of:
        raise ValidationError(
            "Refresh the source before creating an action from today's observation."
        )
    current = current_source(session, scope, as_of, source_type, code, key)
    if current is None or current["state"] != "current":
        raise ValidationError(
            "This source is not currently available in the authorized project. Refresh the source."
        )
