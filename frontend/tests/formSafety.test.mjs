import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";

function moduleAt(file, dependencies = {}, globals = {}) {
  const exports = {};
  const code = ts.transpileModule(readFileSync(new URL(file, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  runInNewContext(`(function(require, exports) { ${code}\n})`, { ...globals })(name => dependencies[name], exports);
  return exports;
}
const client = moduleAt("../src/lib/api/client.ts", {}, { fetch: async () => response });
let response;
test("422 retains field paths and row indices; 409 and non-JSON errors keep status", async () => {
  response = new Response(JSON.stringify({ detail: [{ loc: ["body", "installments", 1, "contractual_due_date"], msg: "Invalid date" }] }), { status: 422 });
  await assert.rejects(client.post("/test", {}), error => {
    assert.equal(error.status, 422);
    assert.equal(JSON.stringify(error.fieldErrors), JSON.stringify([{ path: ["installments", 1, "contractual_due_date"], message: "Invalid date" }]));
    return true;
  });
  response = new Response(JSON.stringify({ detail: "Already changed" }), { status: 409 });
  await assert.rejects(client.post("/test", {}), error => error.isConflict && error.message === "Already changed");
  response = new Response("proxy unavailable", { status: 503 });
  await assert.rejects(client.get("/test"), error => error.status === 503 && error.message === "Request failed (503).");
});

// Small hook lifecycle harness: runs the actual reader and its cleanup functions.
// Deferred requests model network order independently of render order.
function reader() {
  const slots = [];
  let cursor = 0;
  let effects = [];
  const same = (a, b) => a?.length === b.length && b.every((value, index) => Object.is(value, a[index]));
  const react = {
    useState(initial) { const index = cursor++; slots[index] ??= { value: typeof initial === "function" ? initial() : initial }; return [slots[index].value, value => { slots[index].value = typeof value === "function" ? value(slots[index].value) : value; }]; },
    useCallback(fn, deps) { return react.useMemo(() => fn, deps); },
    useMemo(fn, deps) { const index = cursor++; if (!same(slots[index]?.deps, deps)) slots[index] = { deps, value: fn() }; return slots[index].value; },
    useEffect(fn, deps) { const index = cursor++; if (!same(slots[index]?.deps, deps)) { effects.push(() => { slots[index]?.cleanup?.(); slots[index] = { deps, cleanup: fn() }; }); } },
  };
  const { useAnswer } = moduleAt("../src/lib/answer.ts", { react, "./api": client });
  return (enabled, load, deps) => {
    cursor = 0; effects = [];
    const answer = useAnswer(enabled, load, deps);
    effects.forEach(effect => effect());
    return answer;
  };
}
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const settle = () => new Promise(resolve => setImmediate(resolve));
test("new dates hide old amounts immediately; late success and failure cannot overwrite the current request", async () => {
  const render = reader(); const old = deferred(); const current = deferred();
  assert.equal(render(true, () => old.promise, ["project", "2026-09-01"]).status, "loading");
  assert.equal(render(true, () => current.promise, ["project", "2026-09-10"]).status, "loading");
  current.resolve("current amounts"); await settle();
  assert.equal(render(true, () => current.promise, ["project", "2026-09-10"]).data, "current amounts");
  old.reject(new client.ApiError(500, "old error")); await settle();
  assert.equal(render(true, () => current.promise, ["project", "2026-09-10"]).data, "current amounts");
  const stale = deferred(); const newer = deferred();
  render(true, () => stale.promise, ["project", "2026-08-01"]);
  render(true, () => newer.promise, ["project", "2026-07-01"]);
  newer.resolve("newer"); stale.resolve("stale"); await settle();
  assert.equal(render(true, () => newer.promise, ["project", "2026-07-01"]).data, "newer");
});
test("retry, filter round trips and role changes start fresh and preserve denied vs failed", async () => {
  const render = reader(); let calls = 0;
  const load = () => { calls++; return Promise.resolve(calls); };
  render(true, load, ["A"]); await settle();
  assert.equal(render(true, load, ["A"]).data, 1);
  render(true, load, ["B"]);
  assert.equal(render(true, load, ["A"]).status, "loading"); await settle();
  const ready = render(true, load, ["A"]); ready.retry();
  assert.equal(render(true, load, ["A"]).status, "loading"); await settle();
  assert.equal(render(true, load, ["A"]).data, 4);
  assert.equal(render(false, load, ["A"]).status, "off"); assert.equal(calls, 4);
  const fail = () => Promise.reject(new client.ApiError(403, "Refused"));
  render(true, fail, ["C"]); await settle();
  assert.equal(render(true, fail, ["C"]).status, "denied");
});
