# Cutover runbook

Written for the person on shift, not for the person who built this. Every
command is copyable, every refusal below says what to do about it, and nothing
here assumes you have read the source code.

`tests/modules/test_cutover_runbook.py` checks this file against the CLI: the
exit codes, the action names and the flags shown below are asserted to be the
ones the tool actually has. A runbook that has drifted from its tool is worse
than no runbook, because it is followed.

## Before any batch: what an administrator sets up

The batch resolves these. It never creates them, and it refuses when they are
absent — a cutover that can bring a project into existence can bring the wrong
one.

| Prerequisite | Set up where | Why not the batch |
|---|---|---|
| The cutover operator's user account | Admin → Users | A batch that creates its own actor authorises itself. |
| Currencies the batch declares | Settings → Currencies | A currency invented by an import is one nobody chose. |
| The country pack and its thresholds | Settings → Country packs | Jurisdiction configuration is a decision. |
| Reference values (`*_code` vocabularies) | Settings → Reference values | Controlled vocabularies are configuration. |
| Tax rules | Settings → Tax rules | Tax treatment is configuration in force at a date. |
| **The project itself** | Projects → New | Its country pack, currencies, fiscal year and manager are five governance decisions, none extractable from a workbook. |

## Where the data lives

Everything a cutover reads or writes locally goes under **`migration-work/`**,
which is git-ignored. The source extract, the bundle, the manifest, the reject
reports, the evidence. None of it belongs in a repository, on any branch, ever.

## Running a preflight

```sh
python -m scripts.migration preflight \
  --bundle    migration-work/bundle \
  --manifest  migration-work/manifest.json \
  --out       migration-work/evidence \
  --target
```

* `--bundle` and `--manifest` are **required**. Omitting one exits `2`.
* `--out` files the result at `<out>/<batch id>/preflight.json`.
* `--target` adds the checks that need the system being migrated into. **Without
  it the result is `INCOMPLETE`, not `PASS`** — a source-only preflight has
  established half of the question.
* `--json` (before the action) prints one object and nothing else, for a script.

## Exit codes

```text
0   the action passed — every check, both halves
1   the batch may not proceed: a blocking failure, or checks not run
2   the command was wrong (argparse)
3   the run happened but could not be filed — nothing was recorded
```

A script should branch on these and on nothing else. `0` is the only value that
means proceed.

## What each refusal means

| Result or check | What happened | What to do |
|---|---|---|
| `INCOMPLETE` | No `--target`, so the target half never ran. | Re-run with `--target`. Do not proceed on this result. |
| `manifest_readable` FAIL | The manifest is malformed, or declares an unsupported contract version. | Re-seal the bundle. Do not hand-edit a manifest; the hashes will stop matching. |
| `bundle_present` FAIL | The `--bundle` path is not a directory. | Check the path. This is usually a typo, which is why it exits 1 and not 0. |
| `source_unchanged` FAIL | A file's bytes differ from the hash sealed at validation. | **Validate again.** Somebody fixed rejects in the source after validating. The reject report you are holding describes the earlier files. |
| `database_reachable` FAIL | The target did not answer. | Fix connectivity. **The remaining target checks were not attempted** — nothing below that line in the report has been established. |
| `schema_at_expected_head` FAIL | The database is at a different Alembic revision than this checkout expects. | Deploy the matching revision, or check out the code that matches the database. Do not proceed: this code would write to columns whose meaning it has guessed. |
| `project_known` FAIL | The manifest's `project_code` resolves to nothing. | Create the project through the application first, or correct the code in the manifest. |
| `currencies_configured` FAIL | A declared currency is not set up. | Configure it in Settings. There is no FX here; a cutover never converts. |
| `batch_not_applied` FAIL | This batch id already holds a claim in the audit trail. | **Stop.** The batch has already been applied. If the earlier run looked incomplete, that is a restore-and-investigate, not a second apply. |
| Exit `3` | The evidence artifact already exists at that path. | Move or remove the earlier file deliberately, or point `--out` somewhere else, then run again. The result you just saw was **not recorded**. |

## Applying a batch

`apply` does not exist. When it does, it will:

* re-verify every hash before writing anything;
* claim the batch and hold **one transaction** for everything it writes, so the
  claim and the data are durable together or neither is;
* refuse a batch that already holds a claim;
* record itself in `audit_events` as a `cutover` action under the batch
  correlation id, so an imported batch can never be mistaken for somebody
  having done the work through the application.

Those pieces exist and are tested. The action that uses them does not, because
a cutover command that accepts `apply` and quietly does nothing is discovered at
the moment somebody believes a batch has landed.

## If something goes wrong

1. **Do not re-run apply.** The claim exists to stop that, and it will.
2. Take the evidence directory. It has the manifest, the hashes and the
   preflight result for the batch.
3. Restore from the pre-cutover backup. There is no partial undo, by design: a
   batch is one transaction, so a failed one left nothing behind, and a
   committed one is complete.
4. If a committed batch is wrong, that is a data correction through the
   application under its own governance — never a second import, and never an
   edit to the audit trail.

## What this runbook cannot tell you yet

How to build the bundle from the client's workbook. That is the source mapping,
it does not exist, and no amount of care here substitutes for it.
