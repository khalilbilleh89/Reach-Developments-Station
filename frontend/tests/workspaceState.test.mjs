import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

function workspace(href) {
  let address = new URL(href, "https://reach.example");
  const exports = {};
  const source = ts.transpileModule(readFileSync(new URL("../src/components/shell/registerState.ts", import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const window = { get location() { return address; }, history: { replaceState(_state, _unused, next) { address = new URL(next, address); } } };
  const require = name => name === "next/navigation" ? { useSearchParams: () => address.searchParams } : { useMemo: fn => fn() };
  runInNewContext(`(function(require, exports) { ${source}\n})`, { URLSearchParams, window })(require, exports);
  return { ...exports, url: () => address };
}

test("Actions clear removes source restrictions while retaining the portfolio route", () => {
  const state = workspace("/portfolio/?section=actions&source_key=source%3A1&project=p&offset=20&action=a");
  const defaults = { source_key: "", project: "", offset: "", action: "" };
  const [, change] = state.useRegisterFields(defaults);
  change(defaults);
  assert.equal(state.url().pathname, "/portfolio/");
  assert.equal(state.url().search, "?section=actions");
});

test("an explicit All Outlook sources selection survives reload despite the default", () => {
  const state = workspace("/portfolio/?section=outlook");
  const defaults = { kind: "cashflow_forecast", horizon: "90", offset: "" };
  const [, change] = state.useRegisterFields(defaults);
  change({ kind: "", horizon: "30" });
  const reloaded = workspace(state.url().href).useRegisterFields(defaults)[0];
  assert.equal(reloaded.kind, "");
  assert.equal(reloaded.horizon, "30");
});

test("sequential filter and pagination updates compose without losing record identity", () => {
  const state = workspace("/projects/?project=p&section=collections&account=sale");
  const [, filters] = state.useRegisterFields({ search: "", status: "" });
  const [, pages] = state.useRegisterFields({ offset: "" });
  filters({ search: "Rana & family" });
  pages({ offset: "200" });
  filters({ status: "overdue" });
  assert.equal(state.url().searchParams.get("search"), "Rana & family");
  assert.equal(state.url().searchParams.get("account"), "sale");
  assert.equal(state.url().searchParams.get("offset"), "200");
  assert.equal(state.url().searchParams.get("status"), "overdue");
});

test("invalid page offsets never become fractional, negative or infinite API offsets", () => {
  const { pageOffset } = workspace("/settings/?section=audit");
  for (const value of ["-1", "1.5", "Infinity", "NaN", "999999999999999999999"]) assert.equal(pageOffset(value), 0);
  assert.equal(pageOffset("200"), 200);
});

test("return-position storage recognizes equivalent queries in a different parameter order", () => {
  const { registerAddress } = workspace("/portfolio/?section=reporting");
  assert.equal(registerAddress("/portfolio/", "section=reporting&project=p&scope=project"),
    registerAddress("/portfolio/", "scope=project&project=p&section=reporting"));
  assert.notEqual(registerAddress("/portfolio/", "offset=20"), registerAddress("/portfolio/", "offset=40"));
});

test("Reporting record views and return retain scope, project and register page", () => {
  const exports = {};
  const source = ts.transpileModule(readFileSync(new URL("../src/components/portfolio/reportingRoutes.ts", import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  runInNewContext(`(function(exports) { ${source}\n})`, { URLSearchParams })(exports);
  const params = new URLSearchParams("section=reporting&scope=project&project=p&offset=20&untrusted=https://evil.example");
  const opened = exports.reportingHref("snapshot", "comparison", "prior", params);
  const board = exports.reportingHref("snapshot", "board", "prior", new URLSearchParams(opened.split("?")[1]));
  const back = exports.reportingHref("", "position", "", new URLSearchParams(board.split("?")[1]));
  assert.equal(back, "/portfolio/?section=reporting&scope=project&project=p&offset=20");
  assert.ok(!opened.includes("untrusted"));
});
