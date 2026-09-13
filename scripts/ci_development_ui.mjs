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
    event.head === 'eng/development-workspace-finish' && event.repository === repository &&
    event.headRepository === repository && paths.length > 0 &&
    paths.every(path => !path.split('/').includes('..') &&
      (path.startsWith('frontend/src/') || path.startsWith('frontend/tests/') || exceptions.has(path)));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const env = process.env;
  const event = { name: env.CI_EVENT, base: env.CI_BASE, head: env.CI_HEAD,
    repository: env.CI_REPOSITORY, headRepository: env.CI_HEAD_REPOSITORY };
  let paths = [];
  if (event.name === 'pull_request' && event.base === 'main' && event.head === 'eng/development-workspace-finish') {
    if (!/^[a-f0-9]{40}$/.test(env.CI_BASE_SHA ?? '') || !/^[a-f0-9]{40}$/.test(env.CI_HEAD_SHA ?? '')) throw new Error('Invalid PR commit identity');
    paths = execFileSync('git', ['diff', '--no-renames', '--name-only', '-z', `${env.CI_BASE_SHA}...${env.CI_HEAD_SHA}`, '--'], { encoding: 'utf8' }).split('\0').filter(Boolean);
  }
  const frontendOnly = isDevelopmentUiOnly(event, paths);
  appendFileSync(env.GITHUB_OUTPUT, `frontend_only=${frontendOnly}\n`);
  console.log(frontendOnly ? 'Approved Development UI delivery: frontend checks only for this PR.' : 'Normal backend and frontend CI policy applies.');
}
