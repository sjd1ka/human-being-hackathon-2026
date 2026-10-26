const assert=require('node:assert/strict');
const {buildMapModel,FIXED_NOTE}=require('./web/agent-map.js');
const AGENTS=[['orchestrator','Orchestrator'],['collector','Evidence Collector'],['evaluator','Evidence Evaluator'],['resolver','Dispute Resolver']];
function run({ran=['orchestrator','collector','evaluator'],kind='real',tools,steps}={}){
 const defaultSteps=[
  {seq:1,role:'coordinator',agent:'orchestrator',action:'start_review',at_ms:0,details:{prior_issues:[]}},
  {seq:2,role:'identity_risk',agent:'collector',action:'inspect_saved_official_observation',at_ms:4,details:{live_check:false}},
  {seq:3,role:'evaluator',agent:'evaluator',action:'request_chronology_resolution',at_ms:9,details:{issue:'pregnant_vs_birth'}}];
 return {run_id:'r1',kind,scenario_type:kind==='real'?'real_public_observations':'synthetic',case_name:'Lucy',status:'pending_evidence',
  duration_ms:1520,steps:steps||defaultSteps,
  tools:tools||[{tool:'hmem',operation:'recall',status:'not_configured',duration_ms:0,memory_id:null}],
  agents:AGENTS.map(([agent,label])=>({agent,label,ran:ran.includes(agent),step_count:ran.includes(agent)?1:0,duration_ms:0,
   decision:ran.includes(agent)?'did a thing':null,skipped_reason:ran.includes(agent)?null:'not needed in this run'}))};
}
const none={run_id:'r1',note:'New review run',model:null};
const model=(r,a=none)=>buildMapModel(r,a);

// cards in flow order, resolver skipped when it did not run
let m=model(run());
assert.deepEqual(m.cards.map(c=>c.agent),['orchestrator','collector','evaluator','resolver']);
assert.deepEqual(m.cards.map(c=>c.label),AGENTS.map(a=>a[1]));
assert.equal(m.cards[3].state,'skipped');
assert.match(m.cards[3].line,/not needed in this run/);
assert.equal(m.cards[0].state,'done');
assert.equal(m.cards[2].state,'warn');// chronology request
assert.equal(m.header,'Run · 3 agents ran · 1.5 s');
assert.equal(model({...run(),duration_ms:7}).header,'Run · 3 agents ran · 7 ms');
assert.equal(m.note,FIXED_NOTE);
assert.equal(FIXED_NOTE,'Agents are code roles in one process. The AI model is used only where marked.');

// no token wording on cards or non-NVIDIA tools
m=model(run(),{...none,model:{route:'nvidia_direct',status:'used',intent:'amount',new_cloud_calls:1,total_tokens:321}});
for(const c of m.cards)assert.ok(!/token/i.test(c.line+c.label+c.duration));
assert.equal(m.tools.length,4);
assert.equal(m.tools[0].text,'NVIDIA Nemotron · 1 call · 321 tokens');
for(const t of m.tools.slice(1))assert.ok(!/token/i.test(t.text));
assert.deepEqual(m.tools.map(t=>t.tool),['nvidia','hmem','zetaris','nightshift']);
assert.equal(m.tools[2].text,'Zetaris · not connected yet');
assert.equal(m.tools[3].text,'Nightshift · not connected');

// tokens only when a call happened
m=model(run(),{...none,model:{route:'nvidia_direct',status:'cached',intent:'amount',new_cloud_calls:0,total_tokens:321}});
assert.equal(m.tools[0].text,'NVIDIA Nemotron · not used');
assert.equal(model(run(),none).tools[0].text,'NVIDIA Nemotron · not used');

// failed or invalid model call: no tokens
for(const status of ['failed','invalid_output']){
 m=model(run(),{...none,model:{route:'nvidia_direct',status,intent:null,new_cloud_calls:1,total_tokens:null}});
 assert.equal(m.tools[0].text,'NVIDIA Nemotron · call failed, answered with fixed phrases');
 assert.ok(!/\d+ tokens/.test(m.tools[0].text));
}

// H-MEM states
assert.equal(model(run()).tools[1].text,'H-MEM · not configured');
m=model(run({tools:[{tool:'hmem',operation:'recall',status:'ok',duration_ms:12,memory_id:'mem-1'},{tool:'hmem',operation:'save',status:'ok',duration_ms:9,memory_id:'mem-2'}]}));
assert.match(m.tools[1].text,/^H-MEM · recall ok/);assert.match(m.tools[1].text,/save ok/);assert.match(m.tools[1].text,/mem-2/);
m=model(run({tools:[{tool:'hmem',operation:'recall',status:'failed',duration_ms:3,memory_id:null}]}));
assert.match(m.tools[1].text,/recall failed/);
m=model(run({tools:[{tool:'hmem',operation:'recall',status:'ok',duration_ms:3,memory_id:null},{tool:'hmem',operation:'save',status:'failed',duration_ms:3,memory_id:null}]}));
assert.match(m.tools[1].text,/save failed/);
assert.match(model(run({tools:[]})).tools[1].text,/not recorded/);

// hostile text stays literal in the log
const hostile='<script>x</script>';
m=model(run({steps:[{seq:1,role:'coordinator',agent:'orchestrator',action:'start_review',at_ms:0,details:{note:hostile}}]}));
assert.ok(JSON.stringify(m.log).includes(hostile));
assert.ok(m.log.orchestrator[0].result.includes(hostile));
assert.deepEqual(Object.keys(m.log).sort(),['collector','evaluator','orchestrator','resolver']);
assert.deepEqual(m.log.resolver,[]);

// sub-role is visible on collector steps
assert.match(model(run()).log.collector[0].text,/identity_risk/);

// fictional label
assert.equal(model(run({kind:'fictional'})).fictional,true);
assert.equal(model(run()).fictional,false);

// no run: only the note, no empty or stale map
m=buildMapModel(null,{run_id:null,note:'Answered from saved results; no agents ran',model:null});
assert.deepEqual(m.cards,[]);
assert.equal(m.header,'Answered from saved results; no agents ran');
assert.equal(m.note,FIXED_NOTE);
assert.equal(m.fictional,false);
assert.deepEqual(m.log,{});

// null funding-style fields are not turned into zero
m=model(run({steps:[{seq:1,role:'coordinator',agent:'orchestrator',action:'x',at_ms:0,details:{remaining_minor:null}}]}));
assert.match(m.log.orchestrator[0].result,/null|not stated/i);

console.log('Agent map model: card order, skipped agents, tool rows, no per-agent tokens, failed model call, H-MEM states, literal hostile text and no-run checks passed.');
