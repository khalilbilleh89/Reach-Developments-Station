"""Read composition: fixed owner batches and globally ordered bounded output."""

from collections.abc import Iterator
from datetime import date, timedelta
from heapq import nsmallest

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.management_actions import batch as actions
from app.modules.portfolio import outlook_schemas as out
from app.modules.portfolio.outlook_sources import observations


def page(
    session: Session,
    scope: Select,
    as_of: date,
    *,
    horizon_days: int,
    limit: int,
    offset: int,
    item_type: str | None = None,
) -> out.Outlook:
    end = as_of + timedelta(days=horizon_days)
    result = out.Outlook(
        as_of=as_of,
        horizon_days=horizon_days,
        horizon_end=end,
        authorized_project_count=session.scalar(select(func.count()).select_from(scope.subquery())),
        limit=limit,
        offset=offset,
    )

    def candidates() -> Iterator[out.Item]:
        yield from observations(
            session, scope, as_of, end, result.coverage, result.currency_buckets
        )
        for action, code, name, owner in actions.due_rows(session, scope, end):
            yield out.Item(
                item_type="management_action_due",
                source_key=f"{action.project_id}:management_action_due:{action.id}:{action.version}:{action.due_date}",
                project_id=action.project_id,
                project_code=code,
                project_name=name,
                title=action.title,
                due_date=action.due_date,
                observation_date=as_of,
                status=action.status,
                owner_user_id=action.owner_user_id,
                owner_display_name=owner,
                basis=(
                    "Open management commitment; overdue items are included. "
                    "Completion never changes the source condition."
                ),
                drilldown=f"/portfolio/?section=actions&action={action.id}",
            )

    def counted() -> Iterator[out.Item]:
        missing: dict[str, set] = {}
        for item in candidates():
            result.summary_counts[item.item_type] = result.summary_counts.get(item.item_type, 0) + 1
            if item.availability != "available":
                missing.setdefault(item.item_type, set()).add(item.project_id)
            if item_type is None or item.item_type == item_type:
                result.total += 1
                yield item
        result.coverage.extend(
            out.Coverage(
                source=kind,
                unavailable_project_count=len(projects),
                reason=(
                    "Current owner basis is unavailable or incomplete; inspect "
                    "the source for the reason."
                ),
            )
            for kind, projects in sorted(missing.items())
        )

    prefix = nsmallest(
        offset + limit,
        counted(),
        key=lambda item: (
            item.due_date or date.max,
            item.project_code,
            str(item.project_id),
            item.item_type,
            item.source_key,
        ),
    )
    result.items = prefix[offset:]
    return result
