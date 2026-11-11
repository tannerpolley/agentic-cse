// Exercise the generated page's actual functions without a server or browser.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import vm from 'node:vm';
const html=readFileSync(process.argv[2],'utf8');
const payload=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const schema=html.match(/<script id="schema" type="application\/json">([\s\S]*?)<\/script>/)[1];
const roots=html.match(/<script id="roots" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script=html.split('<script>').at(-1).split('</script>')[0];
class Element {
  constructor(){this.children=[];this.textContent='';this.value=''}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=nodes}
  setAttribute(){}
  get firstChild(){return this.children[0]}
}
const samples={parse_ms:[],parameters_setup_ms:[],parameters_sort_ms:[],points_sort_ms:[],datasets_setup_ms:[],points_setup_ms:[],sources_setup_ms:[],results_setup_ms:[]};
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
  document.getElementById('roots').textContent=roots;
  const context=vm.createContext({document,Intl,console,setTimeout,clearTimeout});
  vm.runInContext(script,context);
  start=performance.now();vm.runInContext("choose('datasets')",context);samples.datasets_setup_ms.push(performance.now()-start);
  assert(vm.runInContext("filtered.every(r=>r.kind!=='result') && filtered.length===rows.filter(r=>r.kind!=='result').length",context));
  vm.runInContext("get('include-results').checked=true;get('include-results').onchange()",context);
  assert(vm.runInContext('filtered.length===rows.length',context));
  vm.runInContext("get('clear').onclick()",context);
  assert(vm.runInContext("filtered.every(r=>r.kind!=='result')",context));
  assert(!vm.runInContext("visible.datasets.includes('dataset')",context));
  assert.equal(document.getElementById('head').firstChild.children[0].firstChild.textContent,'Project');
  assert(vm.runInContext("rows.every(r=>!roots.some(([project,root])=>project===r.project&&r.path.startsWith(root+'/'))||!relativePath(r).startsWith('/'))",context));
  vm.runInContext("details({path:'<img src=x onerror=alert(1)>',doi:'10.1234/example',dataset:'internal'})",context);
  assert(document.getElementById('details').firstChild.children.some(e=>e.textContent==='<img src=x onerror=alert(1)>'));
  assert(document.getElementById('details').firstChild.children.some(e=>e.children.some(a=>a.href==='https://doi.org/10.1234/example')));
  assert.deepEqual(Array.from(vm.runInContext("values({source_key:'123'},'source_key')",context)),['123']);
  start=performance.now();vm.runInContext("choose('parameters')",context);samples.parameters_setup_ms.push(performance.now()-start);
  start=performance.now();vm.runInContext("sort='value';update()",context);samples.parameters_sort_ms.push(performance.now()-start);
  assert(vm.runInContext('filtered.every((r,i)=>i===0||Number(filtered[i-1].value)<=Number(r.value))',context));
  start=performance.now();vm.runInContext("choose('points')",context);samples.points_setup_ms.push(performance.now()-start);
  start=performance.now();vm.runInContext("sort='value';update()",context);samples.points_sort_ms.push(performance.now()-start);
  assert(vm.runInContext("Object.hasOwn(filters,'unit_source')",context));
  if(vm.runInContext("rows.some(r=>r.unit_source==='column name')",context)){
    assert(document.getElementById('body').children.some(tr=>tr.children.some(td=>td.textContent==='in column name')));
  }
  vm.runInContext('details(rows[0]||{})',context);
  if(vm.runInContext('rows.length>0',context))assert(document.getElementById('details').firstChild.children.some(e=>e.children.some(t=>t.children.length>0)));
  start=performance.now();vm.runInContext("choose('sources')",context);samples.sources_setup_ms.push(performance.now()-start);
  assert(vm.runInContext("rows.length===0||values(rows[0],'project').length>0",context));
  start=performance.now();vm.runInContext("choose('results')",context);samples.results_setup_ms.push(performance.now()-start);
}
const timings=Object.fromEntries(Object.entries(samples).map(([name,values])=>{
  const ordered=values.toSorted((a,b)=>a-b);
  return [name,{median:ordered[Math.floor(ordered.length/2)],min:ordered[0],max:ordered.at(-1),samples:values}];
}));
console.log(JSON.stringify({page_bytes:Buffer.byteLength(html),payload_bytes:Buffer.byteLength(payload),timings},null,2));
