import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(
  new URL(
    "../src/components/projects/payments/PaymentPlanWorkspace.tsx",
    import.meta.url,
  ),
  "utf8",
);
const api = readFileSync(
  new URL("../src/lib/api/index.ts", import.meta.url),
  "utf8",
);

test("an unused draft exposes one reasoned payment-plan deletion", () => {
  assert.match(workspace, /const canDeletePlan = Boolean\(/);
  assert.match(workspace, /!active/);
  assert.match(workspace, /detail\.versions\.length === 1/);
  assert.match(workspace, /Delete payment plan/);
  assert.match(workspace, /The sale itself will not be deleted/);
  assert.match(workspace, /paymentPlans\s*\.deletePlan/);
  assert.match(api, /deletePlan:[\s\S]*payment-plans\/\$\{planId\}/);
});

test("an active plan with a draft exposes discard, while retained history has no delete action", () => {
  assert.match(workspace, /const canDiscardRevision = Boolean\(/);
  assert.match(workspace, /current\.version\.id !== active\.version\.id/);
  assert.match(workspace, /Discard draft revision/);
  assert.match(workspace, /The active schedule will remain unchanged/);
  assert.match(workspace, /paymentPlans\.discardVersion/);
  assert.match(
    workspace,
    /This plan is part of the contractual or financial history and cannot be deleted/,
  );
});
