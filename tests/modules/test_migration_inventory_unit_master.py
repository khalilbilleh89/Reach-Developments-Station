"""Upgrade preserves existing measurements; rollback states its data limits."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_engine
from tests.modules.conftest import approve_areas


def test_existing_measured_areas_survive_the_new_migrations(
    admin_client: TestClient,
    project_id: str,
    unit_id: str,
    area_types: dict[str, str],
    db: Session,
) -> None:
    approve_areas(admin_client, project_id, unit_id, area_types)
    db.rollback()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        command.downgrade(config, "0012_land_classification_text")
        with get_engine().connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM unit_area_values")) == 2
        command.upgrade(config, "head")
        with get_engine().connect() as connection:
            mappings = dict(
                connection.execute(text("SELECT code, physical_component FROM area_types")).all()
            )
            assert mappings == {"INTERNAL": "internal", "BALCONY": None}
            assert connection.scalar(text("SELECT sum(raw_area) FROM unit_area_values")) == 120
            assert connection.scalar(text("SELECT count(*) FROM unit_features")) == 0
    finally:
        command.upgrade(config, "head")
