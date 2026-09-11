import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));
function mount(file, component, dependencies, props) {
  const slots = []; let cursor = 0; let effects = []; const timers = new Map(); let timerId = 0;
  const react = {
    useState(initial) {const i = cursor++; if (!slots[i]) { slots[i] = {value: typeof initial === "function" ? initial() : initial}; slots[i].set = v => {slots[i].value = typeof v === "function" ? v(slots[i].value) : v;}; } return [slots[i].value, slots[i].set];},
    useRef(initial) {const [slot] = react.useState({current:initial}); return slot;},
    useEffect(fn, deps) {const i = cursor++; if (!slots[i] || deps.some((v,n) => v !== slots[i].deps[n])) effects.push(() => {slots[i]?.cleanup?.(); slots[i]={deps,cleanup:fn()};});},
  };
  const exports = {};
  const source = readFileSync(new URL(`../src/components/projects/sales/${file}.tsx`, import.meta.url),"utf8");
  const code = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const ui = new Proxy({}, {get:(_,key) => key});
  runInNewContext(`(function(require,exports){${code}\n})`,{
    crypto:{randomUUID:()=>"request-key"},
    setTimeout(fn) {const id=++timerId; timers.set(id,fn);return id;}, clearTimeout(id){timers.delete(id);},
  })(key => {
    if (key === "react") return react;
    if (key in dependencies) return dependencies[key];
    if (key.startsWith("@/components/ui")) return ui;
    if (key === "@/lib/currency") return {useCurrencyCode:()=>id=>id};
    if (key === "@/lib/format") return {todayISO:()=>"2026-09-11"};
    if (key.startsWith("./") || key.startsWith("@/components/projects/sales")) return new Proxy({}, {get:(_,name)=>name});
    return require(key);
  },exports);
  return {render(){cursor=0;effects=[];const tree=exports[component](props);effects.forEach(fn=>fn());return tree;}, flush(){const list=[...timers.values()];timers.clear();list.forEach(fn=>fn());}};
}
function nodes(tree) {if (!tree || typeof tree !== "object") return [];if (Array.isArray(tree)) return tree.flatMap(nodes);return [tree,...nodes(tree.props?.children)];}
class ApiError extends Error {constructor(message,status=422){super(message);this.status=status;this.fieldErrors=[];}}
const unit = {unit_id:"unit",unit_reference:"A-301",unit_price_version_id:"version",currency_id:"JOD",reference_price_ex_tax:"150000.00"};

test("a late price preview cannot replace the preview for the current agreed price", async()=>{
  const pending=[]; let accepted=null;
  const props={projectId:"project",unitId:"unit",versionId:"version",currencyId:"JOD",value:"143000.00",onChange(){},onPreview(value){accepted=value;}};
  const view=mount("SalesPriceInput","SalesPriceInput",{"@/lib/api":{ApiError,sales:{pricePreview:async()=>new Promise(resolve=>pending.push(resolve))}}},props);
  view.render();view.flush();await settle();
  props.value="160000.00";view.render();view.flush();await settle();
  pending[1]({sales_price_ex_tax:"160000.00",exception_approval_required:false});await settle();
  pending[0]({sales_price_ex_tax:"143000.00",exception_approval_required:true});await settle();
  assert.equal(accepted.sales_price_ex_tax,"160000.00");
  const comparison=nodes(view.render()).find(node=>node.type==="PriceComparison");
  assert.equal(comparison.props.facts.sales_price_ex_tax,"160000.00");
});

test("reservation save validation retains buyer, terms and exact price; double submit is suppressed",async()=>{
  const calls=[];let reject;
  const view=mount("ReservationForm","ReservationForm",{"@/lib/api":{ApiError,sales:{clients:async()=>[{id:"buyer",display_name:"Buyer",client_number:"B1"}],createReservation:async(_,payload)=>{calls.push(payload);return new Promise((_,no)=>{reject=no;});}}}},
    {projectId:"project",unitId:"unit",currencyId:"JOD",unitOption:unit,onCreated(){throw Error("Unexpected success");},onCancel(){},onChangeUnit(){}});
  view.render();await settle();
  const field=(name)=>nodes(view.render()).find(node=>node.props?.name===name);
  field("client_id").props.onChange({target:{value:"buyer"}});
  field("expires_on").props.onChange({target:{value:"2026-10-01"}});
  field("price_locked_until").props.onChange({target:{value:"2026-10-01"}});
  let price=nodes(view.render()).find(node=>node.type==="SalesPriceInput");
  price.props.onChange("143000.25");
  price=nodes(view.render()).find(node=>node.type==="SalesPriceInput");
  price.props.onPreview({sales_price_ex_tax:"143000.25"});
  const form=nodes(view.render()).find(node=>node.type==="form");
  const first=form.props.onSubmit({preventDefault(){}});
  await form.props.onSubmit({preventDefault(){}});
  assert.equal(calls.length,1);
  assert.equal(calls[0].sales_price_ex_tax,"143000.25");
  assert.equal(calls[0].expected_price_version_id,"version");
  assert.equal(calls[0].creation_request_id,"request-key");
  reject(new ApiError("Correct the expiry"));await first;
  assert.equal(field("client_id").props.value,"buyer");
  assert.equal(field("expires_on").props.value,"2026-10-01");
  assert.equal(nodes(view.render()).find(node=>node.type==="SalesPriceInput").props.value,"143000.25");
});

test("ordinary Sales workflow has a Sales API boundary and Inventory has no commercial creation",()=>{
  for(const file of ["../src/components/projects/SalesTab.tsx","../src/components/projects/sales/NewReservation.tsx","../src/components/projects/sales/ReservationForm.tsx","../src/components/projects/sales/SaleWorkspace.tsx"]){
    const source=readFileSync(new URL(file,import.meta.url),"utf8");
    assert.doesNotMatch(source,/inventory\.(?:phases|unit|units)\(/);
  }
  const inventory=readFileSync(new URL("../src/components/projects/inventory/UnitWorkspace.tsx",import.meta.url),"utf8");
  assert.doesNotMatch(inventory,/<(?:ReservationForm|RegisterBuyerSaleForm)\b/);
  const sales=readFileSync(new URL("../src/components/projects/SalesTab.tsx",import.meta.url),"utf8");
  assert.match(sales,/sales\.transactions\(/);
  assert.doesNotMatch(sales,/sales\.register\(/);
});
