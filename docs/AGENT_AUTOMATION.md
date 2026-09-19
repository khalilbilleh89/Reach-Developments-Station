# Agent automation

Four layers decide what a coding agent may do in this repository, and each one
answers a question the others cannot.

| Layer | Holds | Where |
| --- | --- | --- |
| **Skills** | Specialised knowledge and judgement, loaded when the task matches | `.claude/skills/*/SKILL.md` |
| **Permanent policy** | The rules that apply to every change | `CLAUDE.md`, `AGENTS.md`, `docs/ENGINEERING_RULES.md` |
| **Guard scripts** | Deterministic decisions any agent or human can reuse | `scripts/agent_guard.py`, `scripts/agent_preflight.py` |
| **CI** | The authoritative merge evidence, whatever produced the change | `.github/workflows/ci.yml` |

`.claude/settings.json` is not on that list on purpose. It is an **adapter**:
it tells Claude Code when to invoke the guard scripts. It holds no rule of its
own, so Codex, another agent, a human or CI can reach exactly the same
decisions by calling the scripts directly.

## What belongs where

- *"Design the page around the decision the reader is making."* → a **skill**.
  It needs judgement, and a script cannot have any.
- *"Never push to `main`."* → a **guard**. It is deterministic, so a computer
  should decide it rather than an agent remembering to.
- *"Agents do not merge."* → **policy**, in `AGENTS.md` and `CLAUDE.md`, *and*
  a guard, because a rule only an agent can choose to follow is a suggestion.
- *"Required checks pass on the exact head before merge."* → **CI**. It must
  hold regardless of which tool produced the change, so it cannot live on any
  one developer's machine.

## The hooks

`.claude/settings.json` configures three:

| Event | Matcher | Runs | Effect |
| --- | --- | --- | --- |
| `PreToolUse` | `Bash\|PowerShell` | `agent_guard.py shell` | Blocks destructive commands, force pushes, pushes to `main`, `gh pr merge` |
| `PreToolUse` | `Edit\|Write\|NotebookEdit` | `agent_guard.py write` | Blocks edits while on `main`, and writes to local secret files |
| `PreToolUse` | `mcp__.*merge_pull_request` | `agent_guard.py shell` | Blocks merging through the GitHub API |
| `Stop` | — | `agent_preflight.py --hook` | Reports cheap problems before the agent says "done" |

There is deliberately **no** `PostToolUse` hook. Formatting a file immediately
after an agent writes it leaves the agent's view of that file stale, and the
next edit fails against content it did not write. Formatter drift is reported
by the preflight instead, where it costs nothing and confuses nothing.

### What is blocked

`rm -rf` and its flag spellings, PowerShell `Remove-Item -Recurse -Force`,
`git reset --hard`, `git clean -f`, `git push --force` / `-f` / a `+refspec`,
any push whose destination resolves to `main` (including a bare `git push`
while `main` is checked out), `gh pr merge`, merging through the GitHub API,
editing any repository file while on `main`, and writing `.env`, `.env.local`
or `.env.production`.

A compound command is split first, so `git status && git push --force` is
blocked on its second half.

### What is deliberately allowed

`git status`, `diff`, `log`, `fetch`, `pull`, `checkout`, `switch`, `add`,
`commit`, `git push origin <feature-branch>`, `gh pr create`, `gh pr view`,
`pytest`, `ruff`, `npm test`, `npm run lint`, `npm run build`, a non-recursive
`rm`, and `.env.example`.

Two allowances are worth stating outright, because they are decisions rather
than oversights:

- **`git push --force-with-lease` is allowed.** It is the safe form: it refuses
  when the remote moved under you. Blocking it would push people towards bare
  `--force`, which is the opposite of the point.
- **`render.yaml` and other tracked infrastructure are writable.** The guard
  protects secrets, not infrastructure development. Those changes go through a
  reviewed pull request like anything else.

A guard that blocks ordinary work gets switched off, and a guard that is
switched off protects nothing.

## Running the preflight

```bash
python scripts/agent_preflight.py
```

Scoped to the files this branch changes. It runs `git diff --check`, looks for
conflict markers and tracked secret files, parses changed JSON, validates
`.claude/settings.json` and any changed `SKILL.md`, and runs Ruff and ESLint
against the changed files only. Exit `0` is clean, `1` means findings.

Tooling that is not installed is reported as **unavailable**, not as a pass —
a check that could not run has proved nothing.

## Why the logic is not in `.claude/`

Putting the rules in `.claude/hooks/` would make them Claude's rules. They are
the repository's. Any agent that reads `AGENTS.md` is pointed at the same
`scripts/agent_preflight.py`; CI can call the same functions; a human can run
them before pushing. One implementation, one place to fix a false positive.

## Debugging a hook

Run the guard by hand with the payload Claude Code would send:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push --force"}}' \
  | python scripts/agent_guard.py shell; echo "exit=$?"
```

Exit `2` blocks the call and the reason is printed on both stdout (as the
hook's JSON) and stderr. Exit `0` allows it. To disable the hooks temporarily,
rename `.claude/settings.json`; nothing else depends on it, and the checks
remain runnable by hand.

The `Stop` hook blocks at most once per distinct set of findings per session,
so a problem the agent cannot fix reports itself and then gets out of the way
rather than looping.

## Security

Hooks execute with your permissions, which is why the logic is a small,
reviewed Python module rather than shell strings in a settings file.

- Hook input is treated as hostile. It is parsed as JSON and never interpolated
  into a shell.
- Subprocesses are argument arrays. Nothing is run through `shell=True`.
- The guards never execute, evaluate or import a file the agent named.
- Paths are normalised and resolved before comparison; a path outside the
  repository is left alone rather than guessed about.
- No network access, no secrets, no telemetry, and nothing about a prompt or a
  command is written to disk.

Unreadable hook input **allows** the call rather than blocking every tool call
in the session. The guards reduce accidents; they are not a security boundary,
and CI remains the enforcement layer that does not depend on a local file.

## Adding a hook later

Add one only when the action genuinely needs deterministic automatic
execution. A coding preference belongs in a skill or in the engineering rules;
a hook that fires on every edit is a tax paid on every edit.

When you do add one:

1. Put the decision in `scripts/`, as a pure function over its inputs.
2. Test it in `tests/test_agent_guardrails.py`, both the deny case and the
   ordinary-work case it must not block.
3. Add the adapter entry to `.claude/settings.json`.
4. Classify the new file in `scripts/ci_backend_tests.py`, or it will run the
   entire backend suite on every change.
5. Document it in the table above.
