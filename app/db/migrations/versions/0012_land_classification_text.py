"""Land classification becomes the wording on the record, not a code.

Three columns on ``land_parcels`` stop being reference codes and become text:
``ownership_type_code`` → ``ownership_type``, ``title_status_code`` →
``title_status``, ``zoning_class_code`` → ``zoning``.

**Why the shape was wrong.** Ownership, title status and zoning were validated
against the project's country pack, so a parcel could only be described in
wordings somebody had configured in advance. Real land does not cooperate. A
title office writes "Mortgage release pending"; a planning authority issues
"Residential 4-storey"; a deal is "75% acquired, balance under negotiation".
Faced with a closed list, an operator picks the nearest wrong option and puts
the truth in a notes field, which is how a register stops being the record.

Permit type deliberately did **not** move. It is filtered, counted and reported
on, and left open it becomes "Building Permit", "building permit", "Building
Licence" and "BLDG" inside a month. What PR-V2-01 removes there is the detour
through system-wide Settings, not the vocabulary.

**Data is preserved, and the mapping is deterministic or not made at all.** Each
stored code is resolved against ``reference_values`` using the same precedence
the application uses — a country-scoped value shadows a global one of the same
code — and the *label* that was already on screen becomes the stored text. The
partial unique indexes on ``reference_values`` mean each lookup matches at most
one row, so there is nothing to choose between. A code with no configured value
behind it keeps its own text verbatim: ``FREEHOLD`` is a worse label than
"Freehold" and an infinitely better one than a guess. Nothing is dropped and
nothing is invented.

**The downgrade refuses rather than lying.** Once these columns accept arbitrary
text, some of that text cannot be a 64-character code, and the old model has
nowhere to put it. The alternatives are all dishonest: truncate, null it, or
map everything to some ``OTHER``. So the downgrade reverses what it genuinely
can — text matching a configured label goes back to that label's code, text
that already fits the column goes back as itself — and stops with a count and
an explanation when a value would have to be destroyed to fit. A forward-safe
migration beats a reversible-looking one that loses the record.

Revision ID: 0012_land_classification_text
Revises: 0011_cashflow_reporting
Create Date: 2026-09-05 16:20:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_land_classification_text"
down_revision: str | Sequence[str] | None = "0011_cashflow_reporting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "land_parcels"

#: ``(new column, old column, reference category)``, in the order the model
#: declares them. One tuple drives the whole revision so the three facts cannot
#: fall out of step with each other halfway down the file.
FIELDS: tuple[tuple[str, str, str], ...] = (
    ("ownership_type", "ownership_type_code", "ownership_type"),
    ("title_status", "title_status_code", "title_status"),
    ("zoning", "zoning_class_code", "zoning_class"),
)

#: What the old columns could hold. The representability test on downgrade, and
#: the reason a downgrade can fail at all.
CODE_LENGTH = 64


def _label_for_code(column: str, category: str) -> str:
    """SQL resolving one parcel's stored code to the label that was displayed.

    Country-scoped first, then global, then the code itself — the precedence in
    ``settings.service.require_active_reference_value``, written here as SQL
    because a migration cannot import application code that is free to change
    underneath it. Inactive values resolve too: a parcel recorded under a value
    that has since been retired still displayed that value's label, and this
    revision preserves what was on screen rather than re-deciding it.
    """
    return f"""
        COALESCE(
            (SELECT r.label FROM reference_values r
              WHERE r.category = '{category}'
                AND r.code = p.{column}
                AND r.country_pack_id = (
                    SELECT pr.country_pack_id FROM projects pr WHERE pr.id = p.project_id
                )),
            (SELECT r.label FROM reference_values r
              WHERE r.category = '{category}'
                AND r.code = p.{column}
                AND r.country_pack_id IS NULL),
            p.{column}
        )
    """


def _code_for_text(column: str, category: str) -> str:
    """SQL resolving stored text back to something the old 64-char column holds.

    The exact inverse where one exists: text equal to a configured label becomes
    that label's code, so a value this revision translated round-trips to what
    it was. Anything else is kept verbatim when it fits the column — the old
    column had no foreign key and held whatever the service of the day allowed —
    and resolves to NULL when it does not, which is what
    :func:`downgrade` counts and refuses on.
    """
    return f"""
        COALESCE(
            (SELECT r.code FROM reference_values r
              WHERE r.category = '{category}'
                AND r.label = p.{column}
                AND r.country_pack_id = (
                    SELECT pr.country_pack_id FROM projects pr WHERE pr.id = p.project_id
                )
              LIMIT 1),
            (SELECT r.code FROM reference_values r
              WHERE r.category = '{category}'
                AND r.label = p.{column}
                AND r.country_pack_id IS NULL
              LIMIT 1),
            CASE WHEN length(p.{column}) <= {CODE_LENGTH} THEN p.{column} END
        )
    """


def upgrade() -> None:
    """Apply this revision."""
    bind = op.get_bind()

    for new_column, _old_column, _category in FIELDS:
        op.add_column(TABLE, sa.Column(new_column, sa.String(length=500), nullable=True))

    # Backfill before the old columns go, and before the CHECK constraints
    # arrive: a blank string in the old data would otherwise fail a constraint
    # added first, and the operator would see an integrity error instead of the
    # migration doing the obvious thing with it.
    for new_column, old_column, category in FIELDS:
        bind.execute(
            sa.text(
                f"UPDATE {TABLE} AS p SET {new_column} = {_label_for_code(old_column, category)} "
                f"WHERE p.{old_column} IS NOT NULL AND length(btrim(p.{old_column})) > 0"
            )
        )

    for _new_column, old_column, _category in FIELDS:
        op.drop_column(TABLE, old_column)

    for new_column, _old_column, _category in FIELDS:
        op.create_check_constraint(
            op.f(f"ck_{TABLE}_{new_column}_not_blank"),
            TABLE,
            f"{new_column} IS NULL OR length(btrim({new_column})) > 0",
        )


def downgrade() -> None:
    """Revert this revision, or refuse rather than destroy a classification.

    See the module docstring: text that cannot be a 64-character code has no
    representation in the model this returns to, and every way of forcing it
    into one loses the record of what the title or planning document actually
    said.
    """
    bind = op.get_bind()

    blocking = bind.execute(
        sa.text(
            f"SELECT count(*) FROM {TABLE} AS p WHERE "
            + " OR ".join(
                f"({new_column} IS NOT NULL AND ({_code_for_text(new_column, category)}) IS NULL)"
                for new_column, _old_column, category in FIELDS
            )
        )
    ).scalar_one()
    if blocking:
        raise RuntimeError(
            f"{blocking} land parcel(s) record an ownership, title status or zoning "
            f"description longer than {CODE_LENGTH} characters, or one that matches no "
            "configured reference label. The pre-V2 model stores a code and has nowhere "
            "to put those words, and truncating them, nulling them or mapping them to a "
            "catch-all would each destroy what the title or planning document says. "
            "Shorten or clear those descriptions — or configure a reference value whose "
            "label matches one exactly — and run this downgrade again."
        )

    for new_column, _old_column, _category in FIELDS:
        op.drop_constraint(op.f(f"ck_{TABLE}_{new_column}_not_blank"), TABLE, type_="check")

    for _new_column, old_column, _category in FIELDS:
        op.add_column(TABLE, sa.Column(old_column, sa.String(length=CODE_LENGTH), nullable=True))

    for new_column, old_column, category in FIELDS:
        bind.execute(
            sa.text(
                f"UPDATE {TABLE} AS p SET {old_column} = {_code_for_text(new_column, category)} "
                f"WHERE p.{new_column} IS NOT NULL"
            )
        )

    for new_column, _old_column, _category in FIELDS:
        op.drop_column(TABLE, new_column)
