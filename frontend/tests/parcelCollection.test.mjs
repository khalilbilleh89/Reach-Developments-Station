import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
const require = createRequire(import.meta.url);
const exports = {};
const code = ts.transpileModule(readFileSync(new URL('../src/components/projects/land/ParcelCollection.tsx', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
runInNewContext(`(function(require,exports){${code}\n})`)(name => {
  if (name === '@/components/ui') return new Proxy({}, {get: (_, key) => key});
  if (name === '@/lib/format') return {money: (value, currency) => `${currency} ${value}`, businessDate: value => value ?? 'Not recorded', percent: value => `${value * 100}%`};
  if (name === './presentation') return {measurement: value => value == null ? 'Not recorded' : String(value)};
  return require(name);
}, exports);
function nodes(tree) { if (!tree || typeof tree !== 'object') return []; if (Array.isArray(tree)) return tree.flatMap(nodes); return [tree, ...nodes(tree.props?.children)]; }
function text(tree) { if (tree == null || typeof tree === 'boolean') return ''; if (typeof tree !== 'object') return String(tree); if (Array.isArray(tree)) return tree.map(text).join(' '); return text(tree.props?.children); }
const parcel = {id:'p1',plot_number:'334',land_area:'0',area_unit:'sqm',ownership_share_fraction:null,purchase_price:'123456.78',base_currency_code:'EUR',is_active:true};
test('parcel dossier requires both role access and record financial visibility', () => {
  for (const [canSeeCost, financials_visible] of [[false,true],[true,false],[false,false]]) {
    const tree=exports.ParcelCollection({parcels:[{...parcel,financials_visible}],canSeeCost,onOpen:()=>{}});
    assert.ok(!text(tree).includes('123456.78'));
  }
  assert.ok(text(exports.ParcelCollection({parcels:[parcel],canSeeCost:true,onOpen:()=>{}})).includes('EUR 123456.78'));
});
test('parcel dossier preserves unknown ownership and opens the original record', () => {
  let opened; const tree=exports.ParcelCollection({parcels:[parcel],canSeeCost:false,onOpen:value=>{opened=value;}});
  assert.equal(nodes(tree).find(n=>n.props?.label==='Ownership share').props.value,'Not recorded');
  assert.equal(nodes(tree).find(n=>n.props?.className==='parcel-estate-area').props.children[0].props.children,'0');
  nodes(tree).find(n=>n.type==='Button').props.onClick(); assert.equal(opened,parcel);
});
