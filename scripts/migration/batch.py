"""A batch's identity, and the refusal that stops one being applied twice.

The failure this exists for is mundane and expensive. An operator applies a
batch on cutover night, the connection drops before the terminal says whether it
worked, and they run it again. Without an identity the second run is a second
set of contracts against the same units — or, where a partial unique index
catches it half way through, a rolled-back batch, a very long night, and no
record of which of the two attempts anybody should trust.

**Reach already has the place to record it.** ``audit_events.correlation_id``
groups the events of one operation, and a cutover batch is one operation whose
id arrives in the manifest and does not change between validating and applying.
So the batch's identity needs no table of its own: the presence of a
``cutover.batch_applied`` event carrying the batch id *is* the claim. It is
written inside the same transaction as the data, through the same
``record_event`` contract every other module uses, so a rolled-back apply leaves
no claim behind and a committed one cannot lose its claim. Those two properties
are the whole point, and neither is available to a claim kept anywhere else.

**The refusal is a read, and a read can race.** There is no unique index on
``correlation_id`` and there should not be: the column groups events, so many
rows share one value by design. Two operators starting the same batch at the
same moment could therefore both find nothing and both proceed. The
synchronisation point is the project row, taken through
``projects.service.lock_project`` — the lock this repository already uses for
invariants spanning more than one record, rather than a second mechanism
invented here. Two batches for one project decide in sequence against committed
state; two batches for different projects never contend, which is correct,
because they cannot collide.

Nothing in this module writes domain data. It records that a batch was claimed
and refuses a second claim; what the batch then does is ``apply``'s problem, and
``apply`` does not exist yet.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from app.modules.audit.service import record_event
from app.modules.projects.models import Project
from app.modules.projects.service import lock_project

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.orm import Session

    from scripts.migration.manifest import Manifest

#: What the ``source`` column records for anything this package writes. Declared
#: here rather than beside ``AUDIT_SOURCE_API`` because the column carries no
#: CHECK constraint and audit deliberately owns no closed vocabulary for it —
#: and because a one-time cutover tool naming its own source keeps the import
#: direction one-way. ``app/`` learns nothing about this package, which is the
#: property ``test_cutover_selector.py`` exists to hold.
AUDIT_SOURCE_CUTOVER = "cutover"

#: The action that claims a batch. Read by the duplicate check, so it is a
#: constant rather than a literal in two places.
BATCH_APPLIED = "cutover.batch_applied"

#: The entity type a claim describes. Not a table — deliberately. A batch is an
#: operation, and the audit trail is where operations live.
BATCH_ENTITY_TYPE = "cutover_batch"


class BatchRefused(Exception):
    """The batch may not proceed, and saying why is the whole job."""


class UnknownProject(BatchRefused):
    """The manifest names a project this system does not have."""


class BatchAlreadyApplied(BatchRefused):
    """This batch already holds a claim. Applying it again is refused.

    Carries the earlier claim rather than only its id, because the first thing
    an operator asks is *when*, and the second is *who*.
    """

    def __init__(self, batch_id: uuid.UUID, claim: AuditEvent) -> None:
        super().__init__(
            f"Batch {batch_id} was already applied at {claim.occurred_at.isoformat()}. "
            "A batch is applied once. If the earlier run was incomplete, that is a "
            "restore-and-investigate, not a second apply: re-running would duplicate "
            "everything the first run committed."
        )
        self.batch_id = batch_id
        self.claim = claim


def claim_of(session: Session, batch_id: uuid.UUID) -> AuditEvent | None:
    """The claim this batch already holds, or ``None``. Reads, never writes.

    Public because the target-side half of ``preflight`` asks exactly this
    question, and it must be answerable without taking a lock or opening a
    write transaction: an operator checking whether last night's batch landed
    should not be able to change anything by asking.
    """
    return session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.correlation_id == batch_id,
            AuditEvent.action == BATCH_APPLIED,
        )
        .order_by(AuditEvent.occurred_at)
        .limit(1)
    ).first()


def resolve_project(session: Session, project_code: str) -> Project:
    """The project a manifest names, by its business code.

    A manifest is written by a person before the target's database ids are
    necessarily known to them, so the code is what travels. An unknown code is
    a refusal and never a creation: a cutover that can bring a project into
    existence can bring the wrong one.
    """
    project = session.scalars(select(Project).where(Project.code == project_code)).first()
    if project is None:
        raise UnknownProject(
            f"No project has the code {project_code!r}. The project is set up in the "
            "application before a batch runs; a cutover never creates one."
        )
    return project


def describe(manifest: Manifest) -> dict[str, Any]:
    """What the claim records about the batch, and deliberately no more.

    Every field here comes from the manifest — the operator's own declaration —
    and none from the source data, so no buyer name, identifier or amount can
    reach the audit trail through this path. The file hashes are included
    because they are the evidence that answers "were the bytes applied the bytes
    validated?" months later, when the bundle is gone.
    """
    return {
        "batch_id": str(manifest.batch_id),
        "project_code": manifest.project_code,
        "source_system": manifest.source_system,
        "extracted_at": manifest.extracted_at.isoformat(),
        "cutover_date": manifest.cutover_date.isoformat(),
        "expected_currencies": list(manifest.expected_currencies),
        "operator": manifest.operator,
        "contract_version": manifest.contract_version,
        "adapter_version": manifest.adapter_version,
        "files": [source.as_dict() for source in manifest.files],
    }


def claim(session: Session, manifest: Manifest, *, actor_user_id: uuid.UUID) -> AuditEvent:
    """Claim this batch, or refuse because it is already claimed.

    Order matters and is the substance of this function. The project row is
    locked *before* the duplicate check, so the check reads committed state that
    cannot change under it; without the lock, two concurrent applies would each
    read "not applied" and each proceed.

    Does not commit — the same contract ``record_event`` keeps. The caller owns
    the transaction, so the claim and whatever the batch writes become durable
    together or not at all. A claim that could commit ahead of its data would
    refuse the retry of a batch that never landed.
    """
    project = resolve_project(session, manifest.project_code)
    lock_project(session, project.id)

    existing = claim_of(session, manifest.batch_id)
    if existing is not None:
        raise BatchAlreadyApplied(manifest.batch_id, existing)

    return record_event(
        session,
        action=BATCH_APPLIED,
        entity_type=BATCH_ENTITY_TYPE,
        entity_id=manifest.batch_id,
        correlation_id=manifest.batch_id,
        actor_user_id=actor_user_id,
        reason=manifest.reason,
        source=AUDIT_SOURCE_CUTOVER,
        before=None,
        after=describe(manifest),
    )
