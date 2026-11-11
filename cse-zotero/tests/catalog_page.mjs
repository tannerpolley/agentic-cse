// Exercise the generated page's actual functions without a server or browser.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import vm from 'node:vm';
const html=readFileSync(process.argv[2],'utf8');
const payload=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const schema=html.match(/<script id="schema" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script=html.split('<script>').at(-1).split('</script>')[0];
class Element {
  constructor(){this.children=[];this.textContent='';this.value=''}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=nodes}
  setAttribute(){}
  get firstChild(){return this.children[0]}
}
const samples={parse_ms:[],parameters_setup_ms:[],parameters_sort_ms:[],points_sort_ms:[]};
for(let iteration=0;iteration<Number(process.argv[3]||1);iteration++){
  global.gc?.();
  let start=performance.now(), parsed=JSON.parse(payload);
  samples.parse_ms.push(performance.now()-start);
  assert(parsed.datasets.every(row=>!Object.hasOwn(row,'metadata')));
  parsed=null;
  global.gc?.();
  const elements=new Map();
  const document={createElement:()=>new Element(),getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id)}};
  document.getElementById('data').textContent=payload;
  document.getElementById('schema').textContent=schema;
  const context=vm.createContext({document,Intl,console,setTimeout,clearTimeout});
  vm.runInContext(script,context);
  assert(document.getElementById('head').firstChild.children.some(th=>th.firstChild.textContent==='duplicate_of'));
  assert.deepEqual(Array.from(vm.runInContext("values({source_key:'123'},'source_key')",context)),['123']);
  start=performance.now();vm.runInContext("choose('parameters')",context);samples.parameters_setup_ms.push(performance.now()-start);
  start=performance.now();vm.runInContext("sort='value';update()",context);samples.parameters_sort_ms.push(performance.now()-start);
  assert(vm.runInContext('filtered.every((r,i)=>i===0||Number(filtered[i-1].value)<=Number(r.value))',context));
  vm.runInContext("choose('points')",context);
  start=performance.now();vm.runInContext("sort='value';update()",context);samples.points_sort_ms.push(performance.now()-start);
  assert(vm.runInContext("Object.hasOwn(filters,'unit_source')",context));
  if(vm.runInContext("rows.some(r=>r.unit_source==='column name')",context)){
    assert(document.getElementById('body').children.some(tr=>tr.children.some(td=>td.firstChild.textContent==='in column name')));
  }
  vm.runInContext("choose('sources')",context);
  assert(vm.runInContext("rows.length===0||values(rows[0],'project').length>0",context));
}
const timings=Object.fromEntries(Object.entries(samples).map(([name,values])=>{
  const ordered=values.toSorted((a,b)=>a-b);
  return [name,{median:ordered[Math.floor(ordered.length/2)],min:ordered[0],max:ordered.at(-1),samples:values}];
}));
console.log(JSON.stringify({page_bytes:Buffer.byteLength(html),payload_bytes:Buffer.byteLength(payload),timings},null,2));
