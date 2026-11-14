import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
function harness() {
  const slots = []; let cursor = 0;
  const source = readFileSync(new URL("../src/components/projects/ConsultantEngineerTab.tsx", import.meta.url), "utf8") + "\nexport { ConsultantDialog };";
  const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`)((key) => {
    if(key === "react") return { useState(initial) {const i=cursor++;slots[i]??={value:typeof initial === "function" ? initial() : initial};return [slots[i].value,value=>{slots[i].value=typeof value === "function" ? value(slots[i].value) : value;}];} };
    if(key === "@/components/ui") return new Proxy({}, {get:(_,name)=>name});
    if(key.startsWith("@/") || key.startsWith("./design/")) return {};
    return require(key);
  },exports);
  return {render(props){cursor=0;return exports.ConsultantDialog(props);}};
}
function nodes(tree){if(!tree||typeof tree!=="object")return [];if(Array.isArray(tree))return tree.flatMap(nodes);return [tree,...nodes(tree.props?.children)];}
const row={id:"agreement",engagement_type:"main",consultant_name:"Synthetic Studio",agreement_reference:"TEST-01",status:"active"};
const selector=tree=>nodes(tree).find(node=>node.type==="select"&&node.props["aria-label"]==="engagement type");
test("existing engagement dropdown edits and reopens the saved type",()=>{
  const h=harness();let saved;
  const props={editor:{kind:"engagement",row},stages:[],disciplines:[],busy:false,error:null,onCancel(){},onSubmit(body){saved=body;}};
  let tree=h.render(props);assert.equal(selector(tree).props.disabled,undefined);
  assert.deepEqual(nodes(selector(tree)).filter(node=>node.type==="option").map(node=>node.props.children),["Main consultant","Sub-consultant"]);
  selector(tree).props.onChange({target:{value:"subconsultant"}});
  tree=h.render(props);assert.equal(selector(tree).props.value,"subconsultant");
  nodes(tree).find(node=>node.type==="form").props.onSubmit({preventDefault(){}});
  assert.equal(saved.engagement_type,"subconsultant");assert.equal(saved.consultant_name,row.consultant_name);
  const reopened=harness().render({...props,editor:{kind:"engagement",row:{...row,...saved}}});
  assert.equal(selector(reopened).props.value,"subconsultant");
});
