import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createRequire} from "node:module";
import {runInNewContext} from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const code = ts.transpileModule(readFileSync(new URL("../src/components/projects/inventory/UnitRemovalAction.tsx", import.meta.url), "utf8"), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX},
}).outputText;

test("Unit removal is owner-only and submits the scoped unit and reason", async () => {
  const calls = [], exports = {};
  runInNewContext(`(function(require, exports) { ${code}\n})`)(name => {
    if (name === "@/lib/api") return {inventory: {deleteRecord: async (...args) => calls.push(args)}};
    if (name === "../DeleteRecordButton") return {DeleteRecordButton: "DeleteRecordButton"};
    return require(name);
  }, exports);
  let refreshed = 0;
  const props = {projectId: "project", unitId: "unit", reference: "1102", onRemoved: async () => {refreshed++;}};
  for (const roles of [[], ["system_admin"], ["sales_operations"], ["system_admin", "approver_cfo", "project_manager"]]) {
    assert.equal(exports.UnitRemovalAction({...props, roles: new Set(roles)}), null);
  }
  const action = exports.UnitRemovalAction({...props, roles: new Set(["master_admin"])});
  assert.equal(action.props.recordName, "1102");
  assert.equal(action.props.confirmLabel, "Delete from Inventory & Sales");
  assert.equal(action.props.destructive, true);
  assert.match(action.props.description, /remain in history/);
  await action.props.onDelete("Duplicate");
  assert.deepEqual(calls, [["project", "units", "unit", "Duplicate"]]);
  await action.props.onDeleted();
  assert.equal(refreshed, 1);
});
