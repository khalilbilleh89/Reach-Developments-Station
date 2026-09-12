import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
const settle = () => new Promise(resolve => setImmediate(resolve));
function mount(file, component, dependencies, props) {
  const slots = []; let cursor = 0; let effects = []; const timers = new Map(); let timerId = 0; let focused = null;
  const react = {
    useState(initial) {const i = cursor++; if (!slots[i]) { slots[i] = {value: typeof initial === "function" ? initial() : initial}; slots[i].set = v => {slots[i].value = typeof v === "function" ? v(slots[i].value) : v;}; } return [slots[i].value, slots[i].set];},
    useId() { return react.useState(() => `test-${cursor}`)[0]; },
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
  return {render(){cursor=0;effects=[];const tree=exports[component](props);nodes(tree).forEach(node=>{if(node.props?.ref) node.props.ref.current={focus(){focused=node;}};});effects.forEach(fn=>fn());return tree;}, focused(){return focused;}, flush(){const list=[...timers.values()];timers.clear();list.forEach(fn=>fn());}};
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

const formatExports = {};
runInNewContext(`(function(exports){${ts.transpileModule(readFileSync(new URL("../src/lib/format.ts", import.meta.url), "utf8"), {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText}\n})`)(formatExports);
const inventoryUnit = {...unit, unit_type:"2BR", building_name:"Building A", floor_name:"Floor 3", phase_name:"Phase 1", gross_area:"118.00", area_unit:"m²"};
const textOf = tree => {
  if (tree == null || typeof tree === "boolean") return "";
  if (typeof tree !== "object") return String(tree);
  if (Array.isArray(tree)) return tree.map(textOf).join(" ");
  return textOf(tree.props?.children);
};
const button = (view, label) => nodes(view.render()).find(node => ["Button", "button"].includes(node.type) && textOf(node).includes(label));
function picker(open = true) {
  const pending = []; const selected = []; let cancelled = false;
  const view = mount("SalesUnitPicker", "SalesUnitPicker", {
    "@/lib/api": {ApiError, sales:{unitOptions:(project, query) => new Promise((resolve,reject)=>pending.push({project,query,resolve,reject}))}},
    "@/lib/format": formatExports,
  }, {projectId:"project", onSelect:value=>selected.push(value), onCancel:()=>{cancelled=true;}});
  if (open) {button(view,"Select available unit").props.onClick(); view.render();}
  const search = value => {nodes(view.render()).find(node=>node.type==="input").props.onChange({target:{value}}); view.render(); view.flush();};
  return {view,pending,selected,search,cancelled:()=>cancelled};
}

test("browse-first options display governed details and select the exact unit", async()=>{
  const f=picker(); f.view.render(); f.view.flush();
  assert.equal(f.pending[0].query.search, ""); assert.equal(f.pending[0].query.offset,"0");
  f.pending[0].resolve({items:[inventoryUnit],next_offset:null}); await settle();
  const option=button(f.view,"A-301");
  for(const value of ["2BR","Building A","Floor 3","Phase 1","118.00 m²","JOD 150,000.00","ex tax"]) assert.ok(textOf(option).includes(value));
  assert.equal(option.type,"button"); assert.equal(option.props.type,"button");
  option.props.onClick(); assert.equal(f.selected[0],inventoryUnit);
  assert.equal(button(f.view,"Select available unit").props["aria-expanded"],false);
  assert.equal(nodes(f.view.render()).find(node=>node.type==="input"),undefined);
  assert.equal(button(f.view,"Load more units"),undefined);
  button(f.view,"Cancel").props.onClick(); assert.ok(f.cancelled());
});

test("load more appends, deduplicates and retains units through a recoverable failure",async()=>{
  const f=picker(); f.view.render(); f.view.flush();
  f.pending[0].resolve({items:[inventoryUnit],next_offset:30}); await settle();
  button(f.view,"Load more units").props.onClick(); f.view.render(); f.view.flush();
  assert.equal(f.pending[1].query.offset,"30");
  assert.equal(button(f.view,"Load more units").props.disabled,true);
  assert.ok(button(f.view,"A-301"));
  f.pending[1].reject(new ApiError("Temporary failure")); await settle();
  assert.ok(button(f.view,"A-301")); assert.doesNotMatch(textOf(f.view.render()),/No units|No matching/);
  button(f.view,"Retry").props.onClick(); f.view.render(); f.view.flush();
  assert.equal(f.pending[2].query.offset,"30");
  f.pending[2].resolve({items:[inventoryUnit,{...inventoryUnit,unit_id:"second",unit_reference:"A-302",unit_type:null,gross_area:null}],next_offset:null}); await settle();
  assert.equal(nodes(f.view.render()).filter(node=>node.props?.className==="sales-unit-picker-option").length,2);
  assert.doesNotMatch(textOf(button(f.view,"A-302")),/2BR|118|0 m²/);
  assert.ok(button(f.view,"A-301")); assert.equal(button(f.view,"Load more units"),undefined);
});

test("server search resets offset, hides prior results immediately and ignores late queries",async()=>{
  const f=picker(); f.view.render(); f.view.flush();
  f.pending[0].resolve({items:[inventoryUnit],next_offset:30}); await settle();
  button(f.view,"Load more units").props.onClick(); f.view.render(); f.view.flush();
  f.search("Building B"); assert.equal(button(f.view,"A-301"),undefined);
  assert.equal(f.pending[2].query.offset,"0"); assert.equal(f.pending[2].query.search,"Building B");
  f.search("Phase 2");
  f.pending[3].resolve({items:[{...inventoryUnit,unit_reference:"B-101"}],next_offset:null}); await settle();
  f.pending[2].resolve({items:[inventoryUnit],next_offset:30});
  f.pending[1].resolve({items:[inventoryUnit],next_offset:60}); await settle();
  assert.ok(button(f.view,"B-101")); assert.equal(button(f.view,"A-301"),undefined);
});

for(const query of ["", "unknown", "   "]) test(`empty state for ${JSON.stringify(query)} waits for exhausted eligible inventory`,async()=>{
  const f=picker(); f.search(query);
  f.pending[0].resolve({items:[],next_offset:30}); await settle();
  assert.equal(f.pending[1].query.offset,"30"); assert.doesNotMatch(textOf(f.view.render()),/No units|No matching/);
  f.pending[1].resolve({items:[],next_offset:null}); await settle();
  assert.ok(textOf(f.view.render()).includes(query.trim() ? "No matching available units" : "No units are currently available for reservation"));
});

test("initial failure preserves search and retry can discover units after sparse batches",async()=>{
  const f=picker(); f.search("Building A"); f.pending[0].reject(new ApiError("Unavailable")); await settle();
  assert.doesNotMatch(textOf(f.view.render()),/No units|No matching/);
  assert.equal(nodes(f.view.render()).find(node=>node.type==="input").props.value,"Building A");
  button(f.view,"Retry").props.onClick(); f.view.render(); f.view.flush();
  assert.equal(f.pending[1].query.search,"Building A");
  f.pending[1].resolve({items:[],next_offset:30}); await settle();
  f.pending[2].resolve({items:[inventoryUnit],next_offset:null}); await settle();
  assert.ok(button(f.view,"A-301"));
});

test("New Reservation forwards the selected option to both flows and Change unit remounts a fresh picker",async()=>{
  const view=mount("NewReservation","NewReservation",{"@/lib/format":formatExports},{projectId:"project",allowOwner:true,onCreated(){},onSaleCreated(){},onCancel(){}});
  nodes(view.render()).find(node=>node.type==="SalesUnitPicker").props.onSelect(inventoryUnit);
  let tree=nodes(view.render());
  assert.equal(tree.find(node=>node.type==="ReservationForm").props.unitOption,inventoryUnit);
  assert.ok(/Inventory list price:\s+JOD 150,000.00/.test(textOf(view.render())));
  button(view,"Owner:").props.onClick();
  assert.equal(nodes(view.render()).find(node=>node.type==="RegisterBuyerSaleForm").props.unitOption,inventoryUnit);
  button(view,"Prepare standard reservation").props.onClick();
  nodes(view.render()).find(node=>node.type==="ReservationForm").props.onChangeUnit();
  assert.equal(nodes(view.render()).find(node=>node.type==="SalesUnitPicker").props.initiallyOpen,true);
  assert.equal(nodes(view.render()).find(node=>node.type==="ReservationForm"),undefined);
  const refreshed=picker(); refreshed.view.render(); refreshed.view.flush();
  refreshed.pending[0].resolve({items:[],next_offset:null}); await settle();
  assert.equal(button(refreshed.view,"A-301"),undefined);
});


test("closed selector stays visible without exposing loaded options or search",async()=>{
  const f=picker(false); f.view.render(); f.view.flush();
  const trigger=button(f.view,"Select available unit");
  assert.equal(trigger.type,"button"); assert.equal(trigger.props.type,"button");
  assert.equal(trigger.props["aria-expanded"],false);
  assert.ok(textOf(f.view.render()).includes("Unit"));
  f.pending[0].resolve({items:[inventoryUnit],next_offset:null}); await settle();
  assert.equal(button(f.view,"A-301"),undefined);
  assert.equal(nodes(f.view.render()).find(node=>node.type==="input"),undefined);
  trigger.props.onClick();
  const panel=nodes(f.view.render()).find(node=>node.props?.id===trigger.props["aria-controls"]);
  assert.ok(panel); assert.ok(button(f.view,"A-301"));
  assert.equal(f.view.focused().type,"input");
});

test("global empty inventory keeps a labelled trigger and guidance even while closed",async()=>{
  const f=picker(false); f.view.render(); f.view.flush();
  f.pending[0].resolve({items:[],next_offset:null}); await settle();
  assert.equal(button(f.view,"No available units").props["aria-expanded"],false);
  assert.match(textOf(f.view.render()),/No units are currently available for reservation/);
  assert.match(textOf(f.view.render()),/released for sale and have a current approved price/);
  button(f.view,"No available units").props.onClick();
  assert.ok(nodes(f.view.render()).find(node=>node.type==="input"));
});

test("Escape closes only the open panel, restores trigger focus and retains query on reopening",async()=>{
  const f=picker(); f.search("A-301");
  f.pending[0].resolve({items:[inventoryUnit],next_offset:null}); await settle();
  let prevented=false,stopped=false;
  f.view.render().props.onKeyDown({key:"Escape",preventDefault(){prevented=true;},stopPropagation(){stopped=true;}});
  assert.ok(prevented && stopped);
  assert.equal(f.view.focused().props.className,"sales-unit-picker-trigger");
  assert.equal(button(f.view,"Select available unit").props["aria-expanded"],false);
  button(f.view,"Select available unit").props.onClick();
  assert.equal(nodes(f.view.render()).find(node=>node.type==="input").props.value,"A-301");
  button(f.view,"Select available unit").props.onClick();
  assert.equal(nodes(f.view.render()).find(node=>node.type==="input"),undefined);
});

test("closed request failure preserves the selector and Retry is not an empty state",async()=>{
  const f=picker(false); f.view.render(); f.view.flush();
  f.pending[0].reject(new ApiError("Connection unavailable")); await settle();
  assert.ok(button(f.view,"Select available unit"));
  assert.equal(button(f.view,"No available units"),undefined);
  assert.match(textOf(f.view.render()),/Could not load available units/);
  button(f.view,"Retry").props.onClick(); f.view.render(); f.view.flush();
  f.pending[1].resolve({items:[inventoryUnit],next_offset:null}); await settle();
  button(f.view,"Select available unit").props.onClick();
  assert.ok(button(f.view,"A-301"));
});

test("selected trigger preserves governed details and routes changes through the draft guard",()=>{
  const view=mount("NewReservation","NewReservation",{"@/lib/format":formatExports},{projectId:"project",allowOwner:true,onCreated(){},onSaleCreated(){},onCancel(){}});
  nodes(view.render()).find(node=>node.type==="SalesUnitPicker").props.onSelect(inventoryUnit);
  const trigger=button(view,"A-301");
  assert.ok(trigger.props["data-leaves-editor"]);
  assert.match(textOf(trigger),/2BR · Floor 3/);
  assert.match(textOf(trigger),/JOD 150,000.00/);
  trigger.props.onClick();
  assert.equal(nodes(view.render()).find(node=>node.type==="SalesUnitPicker").props.initiallyOpen,true);
  assert.equal(nodes(view.render()).find(node=>node.type==="ReservationForm"),undefined);
});
