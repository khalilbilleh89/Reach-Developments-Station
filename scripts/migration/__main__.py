"""The cutover's one operational surface.

    python -m scripts.migration preflight --bundle ./work --manifest ./work/manifest.json

Four actions, one entry point, and the safety property is the shape rather than
a flag: **only ``apply`` may write.** Every other action is registered read-only
and there is no option that promotes one — a ``--dry-run`` that has to be
remembered is a ``--dry-run`` that gets forgotten at two in the morning on
cutover night. Running the module with no action prints help and touches
nothing.

``--json`` prints one machine-readable object on stdout and nothing else, so the
runbook can pipe it. Without it the same result is written for a person.

Exit codes are the operational contract:

    0   the action passed
    1   a blocking failure — the batch may not proceed
    2   the command was wrong (argparse)

Actions appear here as they are implemented, not as stubs. A cutover CLI that
accepts ``apply`` and does nothing is worse than one that does not accept it
yet: the first is discovered at the moment somebody believes a batch has landed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.migration import CONTRACT_VERSION
from scripts.migration.manifest import Manifest, ManifestError, load, verify_unchanged

#: A blocking failure. Distinct from argparse's 2, so a runbook can tell "the
#: batch is not safe" from "you typed the command wrong".
EXIT_BLOCKED = 1


@dataclass(frozen=True)
class Action:
    """One thing the operator can ask for, and whether it may write.

    ``writes`` is not documentation. ``test_cutover_cli`` asserts that exactly
    the actions named here as writers are the ones with a write path, so adding
    a silent write to a read-only action fails rather than shipping.
    """

    name: str
    help: str
    writes: bool
    run: Callable[[argparse.Namespace], dict[str, Any]]


def _resolve(argument: str | None, *, what: str) -> Path:
    if argument is None:
        raise SystemExit(f"--{what} is required.")
    return Path(argument).expanduser()


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only: is this batch safe to take further?

    Source-side today — the manifest parses, every declared name is a canonical
    intake name, and every file is present with the hash it was sealed with. The
    target-side checks land with batch identity, because "has this batch already
    been applied?" is a question only the audit trail can answer.
    """
    bundle = _resolve(args.bundle, what="bundle")
    manifest_path = _resolve(args.manifest, what="manifest")

    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})

    manifest: Manifest | None = None
    try:
        manifest = load(manifest_path)
        record(
            "manifest_readable", True, f"{manifest_path} parses under contract {CONTRACT_VERSION}."
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
        help="Read-only. Prove a batch is safe to take further; writes nothing.",
        writes=False,
        run=preflight,
    ),
)

#: The actions that will exist, and whether each may write. Declared here rather
#: than inferred so the write surface is reviewable before the code lands, and
#: so a new action cannot join ``ACTIONS`` without somebody deciding.
WRITE_ACTIONS = frozenset({"apply"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.migration",
        description="One-time legacy cutover tooling. Only 'apply' writes, and it is opt-in.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print one JSON object and nothing else."
    )
    sub = parser.add_subparsers(dest="action")
    for action in ACTIONS:
        child = sub.add_parser(action.name, help=action.help)
        child.add_argument("--bundle", help="Directory holding the canonical intake files.")
        child.add_argument("--manifest", help="Path to the batch manifest.")
        child.add_argument("--out", help="Directory to write reports into.")
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
    if args.out:
        from scripts.migration.reporting import write_json

        write_json(Path(args.out).expanduser() / f"{action.name}.json", payload)
    print(render(payload, as_json=args.json))
    return 0 if payload["result"] == "PASS" else EXIT_BLOCKED


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    sys.exit(main())
