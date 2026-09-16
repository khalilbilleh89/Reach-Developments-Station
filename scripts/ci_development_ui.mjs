import { execFileSync } from 'node:child_process';
import { appendFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const repository = 'khalilbilleh89/Reach-Developments-Station';
const exceptions = new Set([
  'docs/DEVELOPMENT_UI_PLAN.md',
  '.github/workflows/ci.yml',
  'scripts/ci_development_ui.mjs',
  'tests/test_ci_workflow.py',
]);

/** A one-roadmap exception, evaluated over the complete PR diff, including deletions. */
export function isDevelopmentUiOnly(event, paths) {
  return event.name === 'pull_request' && event.base === 'main' &&
    event.head === 'eng/platform-visual-consistency' && event.repository === repository &&
    event.headRepository === repository && paths.length > 0 &&
    paths.every(path => !path.split('/').includes('..') &&
      (path.startsWith('frontend/src/') || path.startsWith('frontend/tests/') || exceptions.has(path)));
}

/**
 * Whether Full may be narrowed to the guards that read the frontend tree.
 *
 * Not a skip and not an exception: every job still runs, and the assignment is
 * still complete over the population it is given. It says only that a diff
 * confined to `frontend/` cannot reach a test that never opens that tree, so
 * asking two hundred module suites about a stylesheet is an hour spent
 * learning nothing.
 *
 * Deliberately narrower than it could be. A push to main is never scoped, so
 * the complete suite still guards the branch everything merges into; a pull
 * request from a fork is never scoped, because its diff is not this
 * repository's to trust; and a diff of nothing is never scoped, because an
 * empty set satisfies `every` and would silently narrow the suite to nothing.
 */
export function isFrontendScoped(event, paths) {
  return event.name === 'pull_request' && event.base === 'main' &&
    event.repository === repository && event.headRepository === repository &&
    paths.length > 0 &&
    paths.every(path => !path.split('/').includes('..') && path.startsWith('frontend/'));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const env = process.env;
  const event = { name: env.CI_EVENT, base: env.CI_BASE, head: env.CI_HEAD,
    repository: env.CI_REPOSITORY, headRepository: env.CI_HEAD_REPOSITORY };
  let paths = [];
  if (event.name === 'pull_request' && event.base === 'main') {
    if (!/^[a-f0-9]{40}$/.test(env.CI_BASE_SHA ?? '') || !/^[a-f0-9]{40}$/.test(env.CI_HEAD_SHA ?? '')) throw new Error('Invalid PR commit identity');
    paths = execFileSync('git', ['diff', '--no-renames', '--name-only', '-z', `${env.CI_BASE_SHA}...${env.CI_HEAD_SHA}`, '--'], { encoding: 'utf8' }).split('\0').filter(Boolean);
  }
  const frontendOnly = isDevelopmentUiOnly(event, paths);
  const frontendScope = isFrontendScoped(event, paths);
  appendFileSync(env.GITHUB_OUTPUT, `frontend_only=${frontendOnly}\n`);
  appendFileSync(env.GITHUB_OUTPUT, `full_scope=${frontendScope ? 'frontend' : 'all'}\n`);
  console.log(frontendOnly ? 'Approved Development UI delivery: frontend checks only for this PR.' : 'Normal backend and frontend CI policy applies.');
  console.log(frontendScope
    ? `Full scope: frontend. All ${paths.length} changed paths are under frontend/, so Full runs the guards that read that tree. Every push to main still runs the complete suite.`
    : 'Full scope: all. Every test file is assigned.');
}
