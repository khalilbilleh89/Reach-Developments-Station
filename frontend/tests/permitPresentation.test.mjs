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
test("the permit screen states one rule about dates and status, and states it correctly",()=>{
 const source=readFileSync(new URL("../src/components/projects/PermitsTab.tsx",import.meta.url),"utf8");
 // The application derives the permit status from the actual milestone dates.
 // This sentence said the opposite, appended to every record-review warning,
 // and taught the operator to maintain by hand a status the server already
 // works out. A screen that contradicts its own behaviour is worse than one
 // that says nothing.
 assert.ok(!source.includes("Dates do not change workflow status automatically"));
 // "Planned, forecast and expiry dates do not change the status" is true and
 // must survive. What may not survive is an *unqualified* denial — one whose
 // subject is dates in general rather than the three kinds that really are
 // inert. So every such claim in the file has to name them.
 for(const claim of source.match(/[A-Z][^.]*dates?[^.]*do(?:es)? not change[^.]*\./g) ?? []){
  assert.match(claim,/planned|forecast|expiry/i,`unqualified denial that dates drive status: ${claim}`);
 }
 // And the rule it does state is the real one, in both directions.
 assert.match(source,/actual milestone dates/i);
 assert.match(source,/Planned,\s*\n?\s*forecast and expiry dates do not change (the )?status/i);
 // The ordinary edit form offers dates, never a status control: entering the
 // date is the whole action.
 assert.ok(!/name: "status"/.test(source));
 for(const field of ["actual_submission_date","accepted_for_review_date","comments_received_date","resubmission_date","issue_date","renewal_date"]) assert.ok(source.includes(field),`${field} is not offered on the permit form`);
 // Manual transition survives for the exceptions no date can express.
 assert.match(source,/Other status changes \(optional\)/);
 assert.match(source,/on hold/i);
});
test("the saved permit reports the status the server derived, and never one the browser worked out",()=>{
 const source=readFileSync(new URL("../src/components/projects/PermitsTab.tsx",import.meta.url),"utf8");
 const save=source.split("onSave={async (changes)")[1].split("onCancel=")[0];
 // The status shown after saving is read off the response and compared with
 // the one that was sent. Nothing here maps a date to a status.
 assert.ok(save.includes("updated.status === before"));
 assert.ok(save.includes("STATUS_LABELS[updated.status]"));
 assert.ok(!/issue_date|TRANSITIONS|completed/.test(save));
});
