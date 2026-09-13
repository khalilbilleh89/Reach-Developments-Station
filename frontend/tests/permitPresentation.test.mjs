import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const exports={};
const code=ts.transpileModule(readFileSync(new URL("../src/components/projects/permits/presentation.ts",import.meta.url),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
runInNewContext(`(function(exports){${code}\n})`)(exports);
test("recorded issue date flags an unstarted permit without changing its status",()=>{
 const permit=Object.freeze({status:"not_started",issue_date:"2025-06-06",expiry_date:"2031-06-06"});
 assert.equal(exports.permitReviewNotes(permit).length,1);
 assert.equal(permit.status,"not_started");
 assert.equal(exports.permitReviewNotes({...permit,status:"issued"}).length,0);
 assert.equal(exports.permitReviewNotes({...permit,issue_date:null}).length,0);
});
test("expiry chronology is flagged independently of workflow status",()=>{
 const notes=exports.permitReviewNotes({status:"issued",issue_date:"2026-09-13",expiry_date:"2026-09-12"});
 assert.equal(notes.length,1); assert.match(notes[0],/expiry date precedes/);
 assert.equal(exports.permitReviewNotes({status:"issued",issue_date:"2026-09-13",expiry_date:"2026-09-13"}).length,0);
});
test("journey highlights only the current workflow family",()=>{
 assert.equal(exports.permitJourneyPosition("preparing"),0);
 assert.equal(exports.permitJourneyPosition("resubmission"),1);
 assert.equal(exports.permitJourneyPosition("rejected"),2);
 assert.equal(exports.permitJourneyPosition("renewed"),3);
 for(const status of ["on_hold","withdrawn","expired","unknown"]) assert.equal(exports.permitJourneyPosition(status),null);
});
