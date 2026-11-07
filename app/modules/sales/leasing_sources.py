"""Minimal client identities and the active sale's buyer, never title evidence or PII."""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.sales.models import Client, SaleContract


def client_relation(project_ids: Select) -> Select:
    return select(
        Client.id, Client.project_id, Client.display_name, Client.client_number, Client.is_active
    ).where(Client.project_id.in_(project_ids))


def active_buyer(
    session: Session, project_id: uuid.UUID, unit_id: uuid.UUID
) -> tuple[dict | None, str | None]:
    row = (
        session.execute(
            select(
                Client.id,
                Client.display_name,
                Client.client_number,
                Client.is_active,
                SaleContract.sale_number,
            )
            .join(SaleContract, SaleContract.client_id == Client.id)
            .where(
                SaleContract.project_id == project_id,
                Client.project_id == project_id,
                SaleContract.unit_id == unit_id,
                SaleContract.status == "active",
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None, None
    return {key: row[key] for key in ("id", "display_name", "client_number", "is_active")}, row[
        "sale_number"
    ]
