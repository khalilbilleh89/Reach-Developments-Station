"""The cutover's one operational surface.

    python -m scripts.migration preflight --bundle ./work --manifest ./work/manifest.json

One entry point, and the safety property is the shape rather than a flag: an
action declares whether it may change the system being migrated into, and
nothing registered here does yet. There is no option that promotes a read-only
action — a ``--dry-run`` that has to be remembered is a ``--dry-run`` that gets
forgotten at two in the morning on cutover night. Running the module with no
action prints help and touches nothing.

The declaration is deliberately narrow, and the narrowness is the point.
``mutates_target`` means *this action changes the target system*. It says
nothing about the filesystem: any action will write its evidence artifact when
the operator passes ``--out``, because a run that cannot leave a record behind
is not much use in a cutover. Those are two different risks and one flag is not
allowed to look like it covers both.

``--json`` prints one machine-readable object on stdout and nothing else, so the
runbook can pipe it. Without it the same result is written for a person.

Exit codes are the operational contract:

    0   the action passed
    1   a blocking failure — the batch may not proceed
    2   the command was wrong (argparse)
    3   the run happened but could not be filed — nothing was recorded

Actions appear here as they are implemented, not as stubs. A cutover CLI that
accepts ``apply`` and does nothing is worse than one that does not accept it
yet: the first is discovered at the moment somebody believes a batch has landed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.migration.manifest import Manifest, ManifestError, load, verify_unchanged

#: A blocking failure. Distinct from argparse's 2, so a runbook can tell "the
#: batch is not safe" from "you typed the command wrong".
EXIT_BLOCKED = 1

#: The run produced a result and could not file it, so there is no artifact for
#: this batch and the runbook's next step is to fix the evidence directory and
#: run it again. Distinct from :data:`EXIT_BLOCKED` because it says nothing
#: about the batch, and distinct from argparse's 2 because the command parsed.
EXIT_UNRECORDED = 3


class EvidenceRefused(Exception):
    """This run's artifact could not be filed, so nothing was recorded."""


@dataclass(frozen=True)
class Action:
    """One thing the operator can ask for, and whether it changes the target.

    ``mutates_target`` is a declaration, not an enforcement. Nothing inspects
    the body of ``run``; the test that pairs this field with
    :data:`TARGET_MUTATION_ACTIONS` proves the two agree and nothing more. What
    that buys is narrow and real — an action cannot become a target writer
    without somebody editing the reviewed set as well, which is where review
    looks. Whether a body honours its declaration is a question for review.
    """

    name: str
    help: str
    mutates_target: bool
    run: Callable[[argparse.Namespace], dict[str, Any]]


def _path(argument: str) -> Path:
    """One operator-supplied path. Whether it was supplied is argparse's job."""
    return Path(argument).expanduser()


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only: is this batch safe to take further?

    Source-side today — the manifest parses, every declared name is a canonical
    intake name, and every file is present with the hash it was sealed with. The
    target-side checks land with batch identity, because "has this batch already
    been applied?" is a question only the audit trail can answer.
    """
    bundle = _path(args.bundle)
    manifest_path = _path(args.manifest)

    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    manifest: Manifest | None = None
    try:
        manifest = load(manifest_path)
        # The manifest's own declared contract, not this code's current one.
        # They are equal today because ``load`` refuses anything else, and the
        # day a second version is supported the report has to say which one this
        # batch was actually proved under rather than which one is newest.
        record(
            "manifest_readable",
            True,
            f"{manifest_path} parses under contract {manifest.contract_version}.",
        )
    except ManifestError as error:
        record("manifest_readable", False, str(error))

    if manifest is not None:
        record(
            "bundle_present",
            bundle.is_dir(),
            f"{bundle} is a directory." if bundle.is_dir() else f"{bundle} is not a directory.",
        )
        if bundle.is_dir():
            try:
                verify_unchanged(manifest, directory=bundle)
                record(
                    "source_unchanged",
                    True,
                    f"All {len(manifest.files)} sealed files hash as they did at validation.",
                )
            except ManifestError as error:
                record("source_unchanged", False, str(error))

    blocking = [check for check in checks if check["result"] == "FAIL"]
    return {
        "action": "preflight",
        "batch_id": str(manifest.batch_id) if manifest else None,
        "project_code": manifest.project_code if manifest else None,
        "cutover_date": manifest.cutover_date.isoformat() if manifest else None,
        "contract_version": manifest.contract_version if manifest else None,
        "checks": checks,
        "blocking": len(blocking),
        "result": "PASS" if not blocking else "FAIL",
    }


#: Every action the CLI offers. ``apply`` is absent until it exists: a cutover
#: command that accepts it and does nothing would be discovered at the moment
#: somebody believed a batch had landed.
ACTIONS: tuple[Action, ...] = (
    Action(
        name="preflight",
        help="Read-only. Prove a batch is safe to take further; changes no target data.",
        mutates_target=False,
        run=preflight,
    ),
)

#: The actions that are allowed to change the system being migrated into.
#: Declared here rather than inferred from :data:`ACTIONS` so the set is
#: reviewable on its own and the two have to be edited together. It is not a
#: statement about files: see the module docstring.
TARGET_MUTATION_ACTIONS = frozenset({"apply"})

#: Where an artifact is filed when the manifest could not be read far enough to
#: name a batch. A fixed name rather than a timestamp, so a second unidentified
#: run refuses rather than quietly filing a second opinion beside the first.
UNIDENTIFIED_BATCH = "unidentified-batch"

#: A batch id is a UUID, and here it becomes a directory name. It arrives as a
#: string out of a result payload, so it is proved to be one rather than trusted
#: to be: joining an unchecked string to the operator's evidence directory is
#: how a run writes outside it.
_BATCH_SEGMENT = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def evidence_path(out: Path, *, action: str, batch_id: str | None) -> Path:
    """Where this run's artifact belongs: under the batch it describes.

    Without the batch segment, two batches preflighted into one evidence
    directory both land on ``preflight.json`` and the second silently replaces
    the first — leaving a file that names a batch nobody would think to check it
    against. The id in the path stops that. A rerun of the *same* batch is
    stopped one step later, by ``write_json`` refusing a file that already
    exists, because a batch replacing its own earlier evidence is the same loss.
    """
    if batch_id is None:
        return out / UNIDENTIFIED_BATCH / f"{action}.json"
    if not _BATCH_SEGMENT.fullmatch(batch_id):
        raise EvidenceRefused(f"{batch_id!r} is not a batch id, so it may not name a directory.")
    return out / batch_id / f"{action}.json"


def file_evidence(out: Path, payload: dict[str, Any], *, action: str) -> Path:
    """Record this run under the batch it describes, or refuse and say so."""
    from scripts.migration.reporting import write_json

    path = evidence_path(out, action=action, batch_id=payload.get("batch_id"))
    try:
        write_json(path, payload)
    except FileExistsError as error:
        raise EvidenceRefused(
            f"{path} already exists, and evidence is not replaced in place. Move or remove the "
            "earlier artifact deliberately, or file this run somewhere else — a directory whose "
            "contents depend on how many times somebody ran the command is not an evidence "
            "chain."
        ) from error
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.migration",
        description="One-time legacy cutover tooling. No action here changes target data.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print one JSON object and nothing else."
    )
    sub = parser.add_subparsers(dest="action")
    for action in ACTIONS:
        child = sub.add_parser(action.name, help=action.help)
        # Required through argparse rather than checked in the action, so a
        # missing path exits 2 — "you typed the command wrong" — instead of 1,
        # which a runbook reads as "this batch is not safe to proceed with".
        child.add_argument(
            "--bundle", required=True, help="Directory holding the canonical intake files."
        )
        child.add_argument("--manifest", required=True, help="Path to the batch manifest.")
        child.add_argument(
            "--out",
            help="Directory to file evidence under, as <out>/<batch id>/<action>.json.",
        )
        child.set_defaults(_action=action)
    return parser


def render(payload: dict[str, Any], *, as_json: bool) -> str:
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)
    lines = [f"{payload['action']}: {payload['result']}"]
    for check in payload.get("checks", []):
        lines.append(f"  {check['result']:4s}  {check['check']} — {check['detail']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    action: Action | None = getattr(args, "_action", None)
    if action is None:
        # No action: help, and nothing touched. This is the default path and it
        # is deliberately the harmless one.
        parser.print_help()
        return 0

    payload = action.run(args)
    refusal: str | None = None
    if args.out:
        try:
            file_evidence(_path(args.out), payload, action=action.name)
        except EvidenceRefused as error:
            refusal = str(error)

    print(render(payload, as_json=args.json))
    if refusal is not None:
        # After the result, so the operator still sees what the run found, and
        # on stderr so ``--json`` remains one object on stdout. The exit code is
        # this run's rather than the batch's: nothing was filed, so the command
        # has to be run again whatever the checks said.
        print(refusal, file=sys.stderr)
        return EXIT_UNRECORDED
    return 0 if payload["result"] == "PASS" else EXIT_BLOCKED


if __name__ == "__main__":  # pragma: no cover - exercised through a subprocess test
    sys.exit(main())
