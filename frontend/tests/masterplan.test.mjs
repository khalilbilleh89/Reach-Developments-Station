import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
const require = createRequire(import.meta.url);
function load() {
  let cursor = 0; const slots = [];
  const react = { useState(initial) { const i = cursor++; slots[i] ??= { value: initial }; return [slots[i].value, value => { slots[i].value = typeof value === 'function' ? value(slots[i].value) : value; }]; } };
  const code = ts.transpileModule(readFileSync(new URL('../src/components/projects/inventory/MasterplanCanvas.tsx', import.meta.url),'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  runInNewContext(`(function(require,exports){${code}\n})`)(name => {
    if (name === 'react') return react;
    if (name === '@/components/ui') return new Proxy({}, {get:(_,key)=>key});
    if (name === './statusLabels') return {statusLabel:s=>({contracted:'Sold',available:'Available'}[s]??s)};
    return require(name);
  },exports);
  return { project: exports.projectPoint, render: props => {cursor=0;return exports.MasterplanCanvas(props);} };
}
const plan = {id:'p1',title:'Synthetic plan',kind:'plan',pixel_width:1000,pixel_height:500,width_m:'100.0000'};
const mapping = {id:'m1',unit_id:'u1',points:[[0.1,0.1],[0.3,0.1],[0.3,0.3],[0.1,0.3]],base_m:'0',height_m:'3'};
const unit = {id:'u1',unit_reference:'A-101',commercial_status:'available'};
function nodes(tree) { if (!tree || typeof tree !== 'object') return []; if (Array.isArray(tree)) return tree.flatMap(nodes); return [tree,...nodes(tree.props?.children)]; }
function text(tree) { if (tree==null || typeof tree==='boolean')return '';if(typeof tree!=='object')return String(tree);if(Array.isArray(tree))return tree.map(text).join(' ');return text(tree.props?.children); }
test('unit geometry is linked by permanent id and keyboard activation opens the same unit',()=>{
 const {render}=load();let selected;
 const tree=render({plan,preview:'/preview',mappings:[mapping],units:[unit],onSelect:m=>selected=m});
 const polygon=nodes(tree).find(n=>n.type==='polygon'&&n.props.role==='button');
 assert.match(polygon.props['aria-label'],/A-101: Available/);
 assert.equal(polygon.props.points,'100,50 300,50 300,150 100,150');
 let prevented=false;polygon.props.onKeyDown({key:'Enter',preventDefault(){prevented=true;}});
 assert.equal(selected.id,'m1');assert.equal(prevented,true);
});
test('current inventory changes update labels and removed units are never shown as available',()=>{
 const {render}=load();const props={plan,preview:'/preview',mappings:[mapping],units:[{...unit,unit_reference:'RENAMED',commercial_status:'contracted'}],onSelect(){}};
 let polygon=nodes(render(props)).find(n=>n.props?.role==='button');assert.match(polygon.props['aria-label'],/RENAMED: Sold/);
 polygon=nodes(render({...props,units:[]})).find(n=>n.props?.role==='button');assert.match(polygon.props['aria-label'],/not in active inventory/i);
});
test('3D uses calibrated metres, actual footprint walls, and bounded camera controls',()=>{
 const {render,project}=load();assert.equal(project([0.5,0.5],30,0.5,0,0)[1],-30);
 const tree=render({plan,preview:'/preview',mappings:[mapping],units:[unit],threeD:true});
 assert.equal(nodes(tree).filter(n=>n.props?.className==='masterplan-wall').length,4);
 assert.ok(nodes(tree).some(n=>n.type==='Field'&&n.props.label==='Rotate'));
 assert.ok(nodes(tree).some(n=>n.type==='Field'&&n.props.label==='Tilt'));
 const uncalibrated=render({plan:{...plan,width_m:null},preview:'/preview',mappings:[mapping],units:[unit],threeD:true});
 assert.equal(nodes(uncalibrated).filter(n=>n.props?.className==='masterplan-wall').length,0);
});
test('render photographs are selectable flat references and never treated as measured 3D',()=>{
 const {render}=load();const tree=render({plan:{...plan,kind:'render'},preview:'/preview',mappings:[mapping],units:[unit],threeD:true});
 assert.equal(nodes(tree).filter(n=>n.props?.className==='masterplan-wall').length,0);
 assert.ok(text(tree).includes('Reset view'));
});
