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
    if (key === "react") return { useId: () => "map-id", useState(initial) {
      const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, value => { slots[i].value = typeof value === "function" ? value(slots[i].value) : value; }];
    }};
    if (key === "@/components/ui") return new Proxy({}, { get: (_, name) => name });
    if (key.includes("DeleteRecordButton")) return { DeleteRecordButton: "DeleteRecordButton" };
    if (key === "./templates") return templatesModule;
    if (key === "./ProcedureMap") return { ProcedureMap: "ProcedureMap" };
    if (key.includes("TeamJobDescription")) return { TeamJobDescription: "TeamJobDescription" };
    if (key === "@/lib/answer") return {};
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

const record = {id:"procedure",version:4,title:"Collections",objective:"Example",sop:"Synthetic",inputs:"Invoice",outputs:"Receipt",steps:[{id:"s",kind:"start",title:"Start",description:"",inputs:"",outputs:"",owner:"",next_id:"e",yes_id:null,no_id:null},{id:"e",kind:"end",title:"End",description:"",inputs:"",outputs:"",owner:"",next_id:null,yes_id:null,no_id:null}]};
const button = (tree,label) => find(tree,"Button").find(n=>n.props.children===label);
test("analysis edits keep a failed save and send saved version",async()=>{
 class ApiError extends Error {} let calls=[]; let closed=false;
 const render=harness("ProcedureTab",{"@/lib/api":{ApiError},"@/lib/api/procedure":{procedures:{update:async(...args)=>{calls.push(args);throw new ApiError("Conflict");}}}});
 const props={projectId:"project",framework:"swot",record,canManage:true,onSaved(){closed=true},onClose(){}};
 let tree=render("ProcedureEditor",props);button(tree,"Edit procedure").props.onClick();tree=render("ProcedureEditor",props);
 find(tree,"input")[0].props.onChange({target:{value:"Revised"}});tree=render("ProcedureEditor",props);
 assert.equal(find(tree,"DraftBoundary")[0].props.dirty,true);
 find(tree,"form")[0].props.onSubmit({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));tree=render("ProcedureEditor",props);
 assert.equal(find(tree,"ValidationSummary")[0].props.error.message,"Conflict");assert.equal(find(tree,"input")[0].props.value,"Revised");assert.equal(calls[0][1].version,4);assert.equal(closed,false);
});
test("readers see diagrams without editing or deletion",()=>{
 const render=harness("ProcedureTab",{"@/lib/api/procedure":{procedures:{}}});const tree=render("ProcedureEditor",{projectId:"project",framework:"swot",record,canManage:false,onClose(){},onSaved(){}});
 assert.equal(find(tree,"ProcedureMap").length,1);assert.equal(button(tree,"Edit procedure"),undefined);assert.equal(button(tree,"Delete procedure"),undefined);
});
test("deletion retains failed confirmation and submits the version and reason",async()=>{
 class ApiError extends Error {} let sent;let done=false;let fail=true;
 const render=harness("ProcedureTab",{"@/lib/api":{ApiError},"@/lib/api/procedure":{procedures:{remove:async(...args)=>{sent=args;if(fail)throw new ApiError("Conflict");}}}});
 const props={projectId:"project",framework:"swot",record,canManage:true,onClose(){},onSaved(){done=true}};
 let tree=render("ProcedureEditor",props);button(tree,"Delete procedure").props.onClick();tree=render("ProcedureEditor",props);
 await find(tree,"PromptDialog")[0].props.onSubmit("Superseded");tree=render("ProcedureEditor",props);assert.equal(find(tree,"PromptDialog")[0].props.error,"Conflict");assert.equal(done,false);
 fail=false;await find(tree,"PromptDialog")[0].props.onSubmit("Superseded");assert.equal(sent[1].version,4);assert.equal(sent[2],"Superseded");assert.equal(done,true);
});

test("walkthrough follows the selected Yes or No route and supports loops",()=>{
 const render=harness("ProcedureMap");
 const values={...record,steps:[{...record.steps[0],next_id:"d"},{...record.steps[0],id:"d",kind:"decision",title:"Paid?",next_id:null,yes_id:"e",no_id:"a"},{...record.steps[0],id:"a",kind:"action",title:"Follow up",next_id:"d"},record.steps[1]]};
 let tree=render("ProcedureMap",{values});button(tree,"Walk through").props.onClick();tree=render("ProcedureMap",{values});
 const next=(label)=>find(tree,"Button").find(n=>Array.isArray(n.props.children)&&n.props.children[0]===label);
 next("Next").props.onClick();tree=render("ProcedureMap",{values});next("No").props.onClick();tree=render("ProcedureMap",{values});assert.ok(JSON.stringify(tree).includes("WALKTHROUGH"));next("Next").props.onClick();tree=render("ProcedureMap",{values});next("Yes").props.onClick();tree=render("ProcedureMap",{values});assert.ok(find(tree,"Notice").some(n=>n.props.children==="End of this path."));
});
