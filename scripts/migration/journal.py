"""One line of operational log, built so it cannot carry somebody's identity.

A cutover runs at night against the client's live commercial data, and the
person watching it wants to know what is happening. The obvious way to tell them
is to log the row that failed. That is also how a buyer's passport number ends
up in a log aggregator, a terminal scrollback, a screenshot in a chat thread and
a support ticket, in that order, none of which anybody thinks about at the time.

So a line is assembled here rather than formatted at the call site, and the
constraints are structural:

* **Only allowlisted keys.** Not "these keys are redacted" — the opposite. A key
  nobody has thought about is refused, because the failure mode of a denylist is
  that the field somebody adds next week is the one carrying the name.
* **Values are identifiers, not prose.** Every allowlisted field is a code, a
  reference, a count or a status. None of them contains a space, an ``@``, or a
  newline, so a value that does is not the field it claims to be — it is a name,
  an email address, or an attempt to forge a second log entry.
* **Refusal is an exception, not a silent drop.** A dropped field leaves the
  operator reading a line that looks complete, and a run that would have logged
  a passport number should stop rather than quietly log less. That is a real
  cost at two in the morning and it is the right one: the alternative is
  discovering the leak after it has been indexed.

What a line looks like::

    batch=6f1c… action=validate source_file=units.csv row=147 reference=SPA-00147
    status=rejected code=UNKNOWN_UNIT

What no line can look like: a buyer's name, an email address, a telephone
number, a bank reference, or a whole source row.
"""

from __future__ import annotations

#: Every key a line may carry, and nothing else. Each names an identifier, a
#: locator, a count or a controlled status — never free text, and never
#: anything a person is identified by.
#:
#: The first seven mirror ``reporting.REJECT_COLUMNS`` because a rejection is
#: the thing most likely to be logged, and a log line that could not say what a
#: reject report says would push somebody into formatting their own.
FIELDS: tuple[str, ...] = (
    # What the reject report carries, minus ``reason`` — see below.
    "source_file",
    "row",
    "reference",
    "field",
    "code",
    "severity",
    # What the operation itself is.
    "batch",
    "action",
    "project",
    "contract",
    "status",
    # How much of it there was.
    "count",
    "rejected",
    "elapsed_ms",
)

#: ``reason`` is deliberately absent. It is the one free-text field on a reject
#: record — a sentence written for a person — and free text is where a value
#: quoted back from the source would travel. The reject report may carry it,
#: because that file is written once and handled deliberately; a log line is
#: copied, pasted and shipped to wherever logs go.
EXCLUDED_FIELDS = frozenset({"reason", "notes", "operator", "name", "email", "phone"})

#: Anything that cannot appear inside a value. A space or an ``@`` means the
#: value is prose or an address rather than the identifier the field promises;
#: a newline or a carriage return would forge a second line in the log.
FORBIDDEN = (" ", "\t", "\n", "\r", "@", '"', "=")

#: A reference is short. A name and address is not, and neither is a source row.
MAX_VALUE = 64


class UnsafeLogLine(Exception):
    """This line may not be written, and saying why is the whole job."""


def _value(key: str, value: object) -> str:
    """One field's value, proved to be an identifier rather than prose."""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if not text:
        raise UnsafeLogLine(
            f"{key} is empty. An empty field reads as a value nobody recorded rather than "
            "one that does not apply; leave it out instead."
        )
    if len(text) > MAX_VALUE:
        raise UnsafeLogLine(
            f"{key} is {len(text)} characters. Every field here is an identifier, a locator "
            f"or a status, and none of those runs past {MAX_VALUE}; a value this long is prose "
            "and prose is where identity travels."
        )
    found = sorted({character for character in FORBIDDEN if character in text})
    if found:
        raise UnsafeLogLine(
            f"{key} contains {found!r}. A space or an '@' means this is a name or an address "
            "rather than the identifier the field promises, and a newline would forge a "
            "second entry in the log."
        )
    return text


def line(**fields: object) -> str:
    """Assemble one log line, or refuse and say which field is the problem.

    Keys are emitted in :data:`FIELDS` order rather than the caller's, so two
    lines describing the same thing read the same way and a change in keyword
    order is not a change in the log. ``None`` values are dropped: a field that
    does not apply is absent rather than recorded as the word "None".
    """
    unknown = sorted(set(fields) - set(FIELDS))
    if unknown:
        raise UnsafeLogLine(
            f"{unknown} is not a field a log line may carry. The allowlist is deliberate: a "
            "denylist would let through whichever field somebody adds next, and that is the "
            "one carrying the name. Add it to FIELDS in a change somebody reviews, or leave "
            "it out."
        )
    return " ".join(
        f"{key}={_value(key, fields[key])}"
        for key in FIELDS
        if key in fields and fields[key] is not None
    )
