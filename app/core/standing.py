"""What was standing then, and what is standing now.

Every governed cash record in this platform has the same three columns —
``status``, ``confirmed_at``, ``reversed_at`` — and every module that reads one
historically has to ask the same question in the same way. Collections receipts
and refunds, construction payments and certificates, and the cashflow module's
own movements are four copies of one rule, and a rule about what a governed
figure *was* is not something four call sites should each restate.

The distinction the rule holds is worth stating plainly, because getting it
wrong is silent.

*Now* is the live position, and the status column answers it. A reversed receipt
is not cash, and the moment somebody withdraws it the current balance must stop
counting it.

*At a cutoff* is a question about the past, and today's status cannot answer it.
A receipt confirmed on 20 August and reversed on 15 September **was** confirmed
on 31 August — that is simply what happened — and a forecast taken as at 31
August was approved with it inside. Filtering that forecast on today's status
would remove the receipt from a basis somebody governed, so re-opening the
August forecast in October would show a smaller figure than the one Finance
approved. The forecast would have been rewritten by an event that happened after
it.

So the historical form asks the two persisted timestamps instead: it had been
confirmed by the cutoff, and it had not yet been reversed by it. A record that
never reached confirmation has no ``confirmed_at`` at all, and ``NULL < bound``
is not true, so drafts and recorded claims stay out without a status test.

One more distinction, which is easy to collapse and expensive to collapse. The
**confirmation timestamp** decides whether a transaction existed at the cutoff.
The **business date** decides which period it belongs to. A receipt dated 31
August and confirmed on 5 September is not in an August forecast at all; once a
September forecast picks it up, it belongs to August. Those are two different
columns answering two different questions, and this module owns only the first.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import ColumnElement, or_
from sqlalchemy.orm import InstrumentedAttribute

#: The status every governed cash record uses for "this money moved".
CONFIRMED = "confirmed"


def as_of_bound(as_of: date) -> datetime:
    """The first instant after ``as_of``, in UTC.

    Exclusive rather than end-of-day inclusive so there is no last-microsecond
    gap to argue about, and one function so that a historical cutoff means the
    same thing in every module — a business date compared against a governed
    timestamp has exactly one correct reading, and several call sites each
    inventing it is several readings waiting to disagree.
    """
    return datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=UTC)


def standing_conditions(
    *,
    status: InstrumentedAttribute[str],
    confirmed_at: InstrumentedAttribute[datetime | None],
    reversed_at: InstrumentedAttribute[datetime | None],
    as_of: date | None,
    confirmed_value: str = CONFIRMED,
) -> list[ColumnElement[bool]]:
    """Which records counted — now, or at a historical cutoff.

    Pass ``as_of=None`` for the live position and a date for a reproducible
    historical one. The columns are passed in rather than the model, because the
    four tables that need this do not share a base class and inventing one so
    they could would be a mixin standing in for three arguments.
    """
    if as_of is None:
        return [status == confirmed_value]
    bound = as_of_bound(as_of)
    return [
        confirmed_at < bound,
        or_(reversed_at.is_(None), reversed_at >= bound),
    ]
