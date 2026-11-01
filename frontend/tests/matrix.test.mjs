import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const templatesModule = {};
runInNewContext(ts.transpileModule(readFileSync(new URL("../src/components/projects/matrix/templates.ts", import.meta.url),"utf8"), {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText, {exports:templatesModule});
function harness(file, mocks = {}) {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL(`../src/components/projects/${file}.tsx`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if (key in mocks) return mocks[key];
    if (key === "react") return { useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }];
    }};
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    if (key.includes("DeleteRecordButton")) return { DeleteRecordButton: "DeleteRecordButton" };
    if (key === "./templates") return templatesModule;
    if (key === "./MatrixCanvas") return { MatrixCanvas: "MatrixCanvas" };
    if (key.includes("TeamJobDescription")) return { TeamJobDescription: "TeamJobDescription" };
    if (key === "@/lib/api") return { ApiError: class ApiError extends Error {} };
    if (key.includes("TeamMemberForm")) return { TeamMemberForm: "TeamMemberForm" };
    if (key.includes("TeamSection")) return { TeamSection: "TeamSection" };
    return require(key);
  }, exports);
  return (name, props) => { cursor = 0; return exports[name](props); };
}
function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return [tree, ...nodes(tree.props?.children), ...nodes(tree.props?.actions)];
}
const find = (tree, type) => nodes(tree).filter(node => node.type === type);

const record = {id:"analysis",project_id:"project",version:4,title:"Market review",framework:"swot",as_of:"2026-10-18",context:"Synthetic",effect:"",growth_threshold_pct:"10",items:[{label:"Existing idea",notes:"Evidence",category:"Strengths",growth_pct:null,relative_share:null}],points:[]};
const button = (tree,label) => find(tree,"Button").find(n=>n.props.children===label);
test("analysis edits keep a failed save and send saved version",async()=>{
 class ApiError extends Error {} let calls=[]; let closed=false;
 const render=harness("matrix/MatrixEditor",{"@/lib/api":{ApiError},"@/lib/api/matrix":{matrices:{update:async(...args)=>{calls.push(args);throw new ApiError("Conflict");}}}});
 const props={projectId:"project",framework:"swot",record,canManage:true,onSaved(){closed=true},onClose(){}};
 let tree=render("MatrixEditor",props);button(tree,"Edit inputs").props.onClick();tree=render("MatrixEditor",props);
 find(tree,"input")[0].props.onChange({target:{value:"Revised"}});tree=render("MatrixEditor",props);
 assert.equal(find(tree,"DraftBoundary")[0].props.dirty,true);
 find(tree,"form")[0].props.onSubmit({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));tree=render("MatrixEditor",props);
 assert.equal(find(tree,"ValidationSummary")[0].props.error.message,"Conflict");assert.equal(find(tree,"input")[0].props.value,"Revised");assert.equal(calls[0][1].version,4);assert.equal(closed,false);
});
test("readers see diagrams without editing or deletion",()=>{
 const render=harness("matrix/MatrixEditor",{"@/lib/api/matrix":{matrices:{}}});const tree=render("MatrixEditor",{projectId:"project",framework:"swot",record,canManage:false,onClose(){},onSaved(){}});
 assert.equal(find(tree,"MatrixCanvas").length,1);assert.equal(button(tree,"Edit inputs"),undefined);assert.equal(button(tree,"Delete analysis"),undefined);
});
test("deletion retains failed confirmation and submits the version and reason",async()=>{
 class ApiError extends Error {} let sent;let done=false;let fail=true;
 const render=harness("matrix/MatrixEditor",{"@/lib/api":{ApiError},"@/lib/api/matrix":{matrices:{remove:async(...args)=>{sent=args;if(fail)throw new ApiError("Conflict");}}}});
 const props={projectId:"project",framework:"swot",record,canManage:true,onClose(){},onSaved(){done=true}};
 let tree=render("MatrixEditor",props);button(tree,"Delete analysis").props.onClick();tree=render("MatrixEditor",props);
 await find(tree,"PromptDialog")[0].props.onSubmit("Superseded");tree=render("MatrixEditor",props);assert.equal(find(tree,"PromptDialog")[0].props.error,"Conflict");assert.equal(done,false);
 fail=false;await find(tree,"PromptDialog")[0].props.onSubmit("Superseded");assert.equal(sent[1].version,4);assert.equal(sent[2],"Superseded");assert.equal(done,true);
});
test("BCG renders server positions with exact source values",()=>{
 const render=harness("matrix/MatrixCanvas");const tree=render("MatrixCanvas",{values:{...record,framework:"bcg",items:[{label:"A",growth_pct:"12.125",relative_share:"1.250",notes:"",category:""}]},points:[{label:"A",category:"Stars",x:410,y:220}]});
 assert.equal(find(tree,"circle")[0].props.cx,410);assert.equal(find(tree,"circle")[0].props.cy,220);const text=JSON.stringify(tree);assert.ok(text.includes("12.125"));assert.ok(text.includes("1.250"));assert.ok(text.includes("Stars"));
});
const byClass = (tree, name) => nodes(tree).filter(node => typeof node.props?.className === "string" && node.props.className.split(" ").includes(name));
const item = (category, label, notes = "") => ({ category, label, notes, growth_pct: null, relative_share: null });
test("SWOT ledger keeps each entry on its side and opens a note in place",()=>{
 const render=harness("matrix/MatrixCanvas");const values={...record,framework:"swot",items:[item("Strengths","Seafront","Beach frontage"),item("Threats","Rates")]};
 let tree=render("MatrixCanvas",{values});
 const forSide=JSON.stringify(byClass(tree,"matrix-ledger-for")[0]);assert.ok(forSide.includes("Seafront"));assert.ok(!forSide.includes("Rates"));
 assert.deepEqual(byClass(tree,"matrix-entry-ref").map(n=>n.props.children),["S1","T1"]);
 byClass(tree,"matrix-entry")[0].props.onClick();tree=render("MatrixCanvas",{values});
 assert.equal(byClass(tree,"matrix-entry")[0].props["aria-expanded"],true);assert.equal(byClass(tree,"matrix-entry-note")[0].props.children,"Beach frontage");
 byClass(tree,"matrix-ledger-head")[0].props.onClick();tree=render("MatrixCanvas",{values});
 assert.equal(byClass(tree,"matrix-ledger-group").filter(n=>n.props.className.includes("matrix-dim")).length,3);
});
test("PESTEL wheel reads one lens at a time and steps round the six",()=>{
 const render=harness("matrix/MatrixCanvas");const values={...record,framework:"pestel",items:[item("Political","Policy review"),item("Economic","Rates rising"),item("Economic","Tourism up")]};
 let tree=render("MatrixCanvas",{values});
 assert.equal(byClass(tree,"matrix-lens-0")[0].props["aria-pressed"],true);assert.ok(JSON.stringify(byClass(tree,"matrix-wheel-panel")[0]).includes("Policy review"));
 find(tree,"button").find(n=>n.props.className==="button button-primary").props.onClick();tree=render("MatrixCanvas",{values});
 assert.equal(byClass(tree,"matrix-wheel")[0].props.style["--matrix-turn"],"60deg");
 const panel=JSON.stringify(byClass(tree,"matrix-wheel-panel")[0]);assert.ok(panel.includes("Tourism up"));assert.ok(!panel.includes("Policy review"));
 assert.ok(JSON.stringify(byClass(tree,"matrix-lens-1")[0]).includes("2 observations"));assert.ok(JSON.stringify(byClass(tree,"matrix-lens-0")[0]).includes("1 observation\""));
});
test("Porter rivalry lights every arrow; an outside force lights its own",()=>{
 const render=harness("matrix/MatrixCanvas");const values={...record,framework:"porter",items:[item("Buyers","Investors compare yields")]};
 let tree=render("MatrixCanvas",{values});
 byClass(tree,"matrix-area-e")[0].props.onClick();tree=render("MatrixCanvas",{values});
 assert.deepEqual(byClass(tree,"matrix-arrow-on").map(n=>n.props.className.includes("matrix-area-ae")),[true]);
 byClass(tree,"matrix-centre")[0].props.onClick();tree=render("MatrixCanvas",{values});
 assert.equal(byClass(tree,"matrix-arrow-on").length,4);
});
test("BCG keeps unplaced products visible until the server places them",()=>{
 const render=harness("matrix/MatrixCanvas");const values={...record,framework:"bcg",items:[{...item("","Studios"),growth_pct:"18",relative_share:"0.6"}]};
 const tree=render("MatrixCanvas",{values,points:[]});
 assert.equal(find(tree,"circle").length,0);assert.equal(byClass(tree,"matrix-card").length,0);
 assert.ok(JSON.stringify(tree).includes("1. Studios (18% · 0.6×)"));
});
test("Ansoff staircase opens on the first step and counts each step's moves",()=>{
 const render=harness("matrix/MatrixCanvas");const values={...record,framework:"ansoff",items:[item("Market penetration","Referrals"),item("Diversification","Retail"),item("Diversification","Hotel")]};
 let tree=render("MatrixCanvas",{values});
 assert.equal(byClass(tree,"matrix-step-0")[0].props["aria-pressed"],true);
 assert.deepEqual(byClass(tree,"matrix-step-count").map(n=>n.props.children),["1 move","0 moves","0 moves","2 moves"]);
 byClass(tree,"matrix-step-3")[0].props.onClick();tree=render("MatrixCanvas",{values});
 const detail=JSON.stringify(byClass(tree,"matrix-stairs-detail")[0]);assert.ok(detail.includes("Hotel"));assert.ok(!detail.includes("Referrals"));
});
test("Fishbone traces a chosen cause into the effect",()=>{
 const render=harness("matrix/MatrixCanvas");const values={...record,framework:"fishbone",effect:"Reservations stalled",items:[item("Process","Three visits","Finance approval waits")]};
 let tree=render("MatrixCanvas",{values});
 assert.equal(byClass(tree,"matrix-trace").length,0);
 byClass(tree,"matrix-cause")[0].props.onClick();tree=render("MatrixCanvas",{values});
 assert.ok(JSON.stringify(byClass(tree,"matrix-trace")[0]).includes("Three visits"));
 assert.equal(byClass(tree,"matrix-funnel-line-on").length,1);assert.equal(byClass(tree,"matrix-funnel-line-dim").length,5);
 assert.ok(JSON.stringify(byClass(tree,"matrix-effect")[0]).includes("Reservations stalled"));
});
