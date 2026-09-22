import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";

const source = path => readFileSync(new URL(path, import.meta.url), "utf8");

test("returned units have a Sales-owned, reasoned action separate from Inventory release", () => {
  const stock = source("../src/components/projects/sales/CommercialUnits.tsx");
  const api = source("../src/lib/api/index.ts");
  assert.match(stock, /"sold","returned"/);
  assert.match(stock, /selected\.commercial_status === "returned"/);
  assert.match(stock, /roles\.has\("sales_operations"\)/);
  assert.match(stock, /selected\.release_blockers\.length>0/);
  assert.match(stock, /sales\.returnUnitToMarket\(projectId,selected\.id,reason\)/);
  assert.match(stock, /<PromptDialog[^>]*title=\{`Return \$\{selected\.unit_reference\} to market`\}/);
  assert.match(api, /returnUnitToMarket:.*\n\s*post<void>\(`/);
  assert.doesNotMatch(stock, /inventory\.transitionUnit\(projectId,selected\.id,\{[^}]*returned/);
});
