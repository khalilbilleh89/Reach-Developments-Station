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

**The two directions are not equally reversible, and the difference is a fact
about the schema rather than a preference.**

*Upgrade — deterministic.* Each stored code is resolved against
``reference_values`` using the same precedence the application uses: a
country-scoped value shadows a global one of the same code. ``code`` is unique
within each scope — ``uq_reference_values_country_scope`` over
``(country_pack_id, category, code)`` and ``uq_reference_values_global_scope``
over ``(category, code)`` where the pack is NULL — so a code matches at most one
row in the scope that applies and there is nothing to choose between. The
*label* that was already on screen becomes the stored text. A code with no
configured value behind it keeps its own text verbatim: ``FREEHOLD`` is a worse
label than "Freehold" and an infinitely better one than a guess.

*Downgrade — only where the reverse mapping is unique.* Nothing constrains
``label``, and nothing should: two codes may legitimately wear the same words
for a person to read. So ``label → code`` is **not** the inverse of
``code → label``. Where a label belongs to exactly one code in the effective
scope, the text goes back to that code and the value round-trips to what it
was. Where it belongs to two, the text no longer records which of them this
parcel held, and the downgrade **refuses**: choosing either would rewrite a
parcel's history to a classification it may never have carried, and it would do
so silently, on rows nobody edited.

Two further refusals, kept distinct because an operator fixes them in different
places. Text that matches no configured label goes back verbatim when it fits
the old 64-character column — that column had no foreign key and held whatever
the service of the day allowed. Text that matches nothing *and* does not fit has
no representation in the model this returns to, and truncating it, nulling it or
mapping it to some ``OTHER`` would each destroy what the title or planning
document says.

A forward-safe migration beats a reversible-looking one that loses the record.

Revision ID: 0012_land_classification_text
Revises: 0011_cashflow_reporting
Create Date: 2026-09-05 16:20:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Callable, Sequence

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

#: A scope, as a SQL predicate over some alias of ``reference_values``. Taking
#: the alias as an argument rather than rewriting a fixed one keeps the
#: correlated "is any *other* code wearing this label" test below honest: the
#: outer row and the row it is compared against must be constrained to the same
#: scope, and a string substitution over ``r.`` would also have caught ``pr.``.
Scope = Callable[[str], str]


def _country_scope(alias: str) -> str:
    """Values belonging to the country pack of this parcel's project."""
    return (
        f"{alias}.country_pack_id = "
        "(SELECT pr.country_pack_id FROM projects pr WHERE pr.id = p.project_id)"
    )


def _global_scope(alias: str) -> str:
    """Values belonging to no country pack."""
    return f"{alias}.country_pack_id IS NULL"


def _label_for_code(column: str, category: str) -> str:
    """SQL resolving one parcel's stored code to the label that was displayed.

    Country-scoped first, then global, then the code itself — the precedence in
    ``settings.service.require_active_reference_value``, written here as SQL
    because a migration cannot import application code that is free to change
    underneath it. Inactive values resolve too: a parcel recorded under a value
    that has since been retired still displayed that value's label, and this
    revision preserves what was on screen rather than re-deciding it.

    A ``COALESCE`` chain is the right shape in *this* direction and only here:
    each subquery matches at most one row, because ``code`` is unique within
    each scope, so falling through to the next scope can only ever mean "the
    first scope had nothing", never "the first scope was undecidable".
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


def _label_matches(column: str, category: str, scope: Scope) -> str:
    """The reference rows in one scope whose label is this parcel's text."""
    return f"r.category = '{category}' AND r.label = p.{column} AND {scope('r')}"


def _scope_has_a_match(column: str, category: str, scope: Scope) -> str:
    """Whether this scope says anything at all about the stored text.

    This is what selects the effective scope, and it is deliberately about
    *matching* rather than about matching unambiguously: a country pack that
    configures this wording twice has still configured it, and the answer to a
    parcel under it is not the global row that happens to be tidier.
    """
    return (
        f"EXISTS (SELECT 1 FROM reference_values r WHERE {_label_matches(column, category, scope)})"
    )


def _sole_code_in(column: str, category: str, scope: Scope) -> str:
    """The code wearing this label in one scope — only when it is the only one.

    No ``LIMIT``, no ``ORDER BY``, no ``min``, no ``sort_order``, no oldest and
    no newest. The row comes back when nothing else in the same scope wears the
    same label and does not come back when something does, so there is nothing
    here that could pick one of two. ``code`` is unique within a scope, so the
    surviving row is also the only row: this is a scalar subquery by
    construction, not by luck.
    """
    return f"""
        (SELECT r.code FROM reference_values r
          WHERE {_label_matches(column, category, scope)}
            AND NOT EXISTS (
                SELECT 1 FROM reference_values other
                 WHERE other.category = r.category
                   AND other.label = r.label
                   AND other.code <> r.code
                   AND {scope("other")}
            ))
    """


def _code_for_text(column: str, category: str) -> str:
    """SQL resolving stored text back to something the old 64-char column holds.

    A ``CASE`` rather than a ``COALESCE`` chain, and the difference is the whole
    correction. ``COALESCE`` treats "this scope is undecidable" and "this scope
    said nothing" as the same answer, so an ambiguous country-scoped label would
    have fallen through to the global scope and then to the raw text — quietly
    writing the *label* into a column that holds *codes*, on a row the guard
    below would have seen nothing wrong with. The effective scope is chosen
    first and then committed to: once a scope has matched, either it yields its
    sole code or this expression is NULL, which is what :func:`downgrade`
    refuses on.

    Text that no scope configures is kept verbatim when it fits the column — the
    old column had no foreign key and held whatever the service of the day
    allowed — and resolves to NULL when it does not.
    """
    return f"""
        CASE
            WHEN {_scope_has_a_match(column, category, _country_scope)}
                THEN {_sole_code_in(column, category, _country_scope)}
            WHEN {_scope_has_a_match(column, category, _global_scope)}
                THEN {_sole_code_in(column, category, _global_scope)}
            ELSE CASE WHEN length(p.{column}) <= {CODE_LENGTH} THEN p.{column} END
        END
    """


def _is_ambiguous(column: str, category: str) -> str:
    """Whether the effective scope matched but could not name a single code.

    Written in terms of the same two expressions :func:`_code_for_text` uses, so
    the guard and the mapping cannot come to disagree about which rows are
    decidable. What keeps that from being circular is the regression test: it
    supplies two codes wearing one label and demands a refusal, so an expression
    that started choosing between them would fail there rather than agree with
    itself here.
    """
    return f"""
        (CASE
            WHEN {_scope_has_a_match(column, category, _country_scope)}
                THEN ({_sole_code_in(column, category, _country_scope)}) IS NULL
            WHEN {_scope_has_a_match(column, category, _global_scope)}
                THEN ({_sole_code_in(column, category, _global_scope)}) IS NULL
            ELSE false
        END)
    """


def _is_unrepresentable(column: str, category: str) -> str:
    """Whether nothing configures this text and it cannot be a code either."""
    return f"""
        (NOT {_scope_has_a_match(column, category, _country_scope)}
         AND NOT {_scope_has_a_match(column, category, _global_scope)}
         AND length(p.{column}) > {CODE_LENGTH})
    """


def _parcels_where(bind: sa.engine.Connection, predicate: Callable[[str, str], str]) -> int:
    """How many parcels have at least one classification satisfying *predicate*."""
    return bind.execute(
        sa.text(
            f"SELECT count(*) FROM {TABLE} AS p WHERE "
            + " OR ".join(
                f"({new_column} IS NOT NULL AND {predicate(new_column, category)})"
                for new_column, _old_column, category in FIELDS
            )
        )
    ).scalar_one()


def _refusal(ambiguous: int, unrepresentable: int) -> str:
    """Why the downgrade stopped, naming every cause that is actually present.

    Two different problems with two different remedies, so they are never
    reported as one — and both are named in the same message when both hold,
    because discovering the second only after resolving the first and running
    the downgrade again is an avoidable second outage.
    """
    reasons: list[str] = []
    if ambiguous:
        reasons.append(
            f"{ambiguous} land parcel(s) record an ownership, title status or zoning "
            "description matching the label of more than one configured code in the scope "
            "that applies to them. The pre-V2 model stores one code, and the text does not "
            "say which one this parcel held: two codes wearing one label are "
            "indistinguishable once only the label is on the record. Restoring either would "
            "rewrite the parcel's history to a classification it may never have carried, on "
            "a row nobody edited. Give those codes labels that differ — or clear the "
            "affected descriptions — and run this downgrade again."
        )
    if unrepresentable:
        reasons.append(
            f"{unrepresentable} land parcel(s) record an ownership, title status or zoning "
            f"description longer than {CODE_LENGTH} characters that matches no configured "
            "reference label. The pre-V2 model stores a code and has nowhere to put those "
            "words, and truncating them, nulling them or mapping them to a catch-all would "
            "each destroy what the title or planning document says. Shorten or clear those "
            "descriptions — or configure a reference value whose label matches one exactly "
            "— and run this downgrade again."
        )
    return " ".join(reasons)


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
    """Revert this revision, or refuse rather than rewrite a classification.

    See the module docstring. Both refusals are decided before a single column
    is added or dropped. What keeps a refused downgrade from leaving a database
    part-way between two models is PostgreSQL's transactional DDL, not this
    ordering — the tests pass with the guard moved below the ALTERs, verified.
    The ordering earns its place for a different reason: a downgrade that is
    going to refuse never takes an ACCESS EXCLUSIVE lock on ``land_parcels``,
    so asking the question costs a running system nothing.
    """
    bind = op.get_bind()

    ambiguous = _parcels_where(bind, _is_ambiguous)
    unrepresentable = _parcels_where(bind, _is_unrepresentable)
    if ambiguous or unrepresentable:
        raise RuntimeError(_refusal(ambiguous, unrepresentable))

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
