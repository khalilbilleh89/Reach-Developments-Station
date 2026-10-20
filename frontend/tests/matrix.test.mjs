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
