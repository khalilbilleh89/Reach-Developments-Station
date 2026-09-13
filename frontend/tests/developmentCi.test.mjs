import assert from 'node:assert/strict';
import test from 'node:test';
import { isDevelopmentUiOnly } from '../../scripts/ci_development_ui.mjs';
const event = { name: 'pull_request', base: 'main', head: 'eng/development-workspace-finish', repository: 'khalilbilleh89/Reach-Developments-Station', headRepository: 'khalilbilleh89/Reach-Developments-Station' };
test('Delivery exception accepts the complete UI stack and its explicit CI governance files', () => {
  assert.equal(isDevelopmentUiOnly(event, ['frontend/src/app/globals.css', 'frontend/tests/landPresentation.test.mjs', 'docs/DEVELOPMENT_UI_PLAN.md', '.github/workflows/ci.yml', 'scripts/ci_development_ui.mjs', 'tests/test_ci_workflow.py']), true);
});
test('Backend, dependency, migration and unrelated workflow changes prevent the exception', () => {
  for (const path of ['app/main.py', 'app/db/migrations/change.py', 'requirements.txt', 'frontend/package.json', '.github/workflows/deploy.yml', 'tests/test_api.py', 'frontend/src/../../app/main.py']) assert.equal(isDevelopmentUiOnly(event, ['frontend/src/app/globals.css', path]), false, path);
  assert.equal(isDevelopmentUiOnly(event, []), false);
});
test('Main pushes, forks and other PR branches keep normal CI', () => {
  for (const change of [{name:'push'}, {base:'integration/mvp3'}, {head:'eng/another-change'}, {head:'eng/property-presentation'}, {head:'eng/development-blue-icons'}, {head:'eng/development-briefing'}, {head:'eng/architectural-property-workspace'}, {head:'eng/development-ui-delivery'}, {head:'eng/visual-02-development-delivery'}, {headRepository:'fork/repo'}, {repository:'other/repo'}]) assert.equal(isDevelopmentUiOnly({...event,...change}, ['frontend/src/app/globals.css']), false);
});
