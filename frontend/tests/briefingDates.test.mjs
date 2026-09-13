import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const exports={};
const code=ts.transpileModule(readFileSync(new URL("../src/components/dashboard/briefing/dates.ts",import.meta.url),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
runInNewContext(`(function(exports){${code}\n})`)(exports);
test("briefing keeps past targets, excludes closed permits, and sorts recorded dates",()=>{
 const rows=exports.briefingDates({permits:[{id:"open",status:"submitted",permit_code:"P1",planned_issue_date:"2020-01-01"},{id:"closed",status:"issued",planned_issue_date:"2019-01-01"},{id:"future",status:"preparing",planned_issue_date:"2030-01-01"},{id:"undated",status:"not_started",planned_issue_date:null}]},null);
 assert.deepEqual(Array.from(rows,row=>row.id),["permit:open","permit:future"]);
 assert.equal(rows[0].date,"2020-01-01");
});
test("briefing uses only active-agreement open work and labels forecast dates",()=>{
 const rows=exports.briefingDates(null,{active_engagement:{id:"active"},stages:[{id:"s",engagement_id:"active",status:"in_progress",name:"Design",forecast_date:"2030-02-01",planned_date:"2030-01-01"},{id:"old",engagement_id:"old",status:"in_progress",planned_date:"2010-01-01"}],deliverables:[{id:"d",engagement_id:"active",status:"submitted",due_date:"2030-01-20"},{id:"a",engagement_id:"active",status:"accepted",due_date:"2000-01-01"}]});
 assert.deepEqual(Array.from(rows,row=>row.id),["deliverable:d","stage:s"]);
 assert.equal(rows[1].date,"2030-02-01");assert.match(rows[1].context,/forecast/);
 assert.equal(exports.briefingDates(null,{active_engagement:null,stages:[],deliverables:[]}).length,0);
});
