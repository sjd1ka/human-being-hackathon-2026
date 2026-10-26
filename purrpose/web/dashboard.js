'use strict';
const api=createPurrposeClient();
const rows=document.getElementById('rows'),detail=document.getElementById('detail');
const status=document.getElementById('status'),empty=document.getElementById('empty');
const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
let selected=null,token=0;
const duration=ms=>ms<1000?ms+' ms':(ms/1000).toFixed(1)+' s';
function hint(text){const p=node('p',text);p.className='empty';detail.replaceChildren(p);}
async function show(runId){
 selected=runId;const mine=++token;
 for(const b of rows.querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.run===runId));
 try{
  const run=await api.run(runId);
  if(mine!==token)return;
  if(run.status==='run_not_found'){hint('This run is no longer stored. Runs are kept in memory, the last 50 only, and cleared on restart.');return;}
  renderAgentMap(detail,buildMapModel(run,{run_id:runId,note:'Run',model:null}));
 }catch(_){if(mine===token)hint('Run details could not be loaded.');}
}
async function load(){
 status.textContent='Loading…';
 try{
  const list=await api.runs();
  rows.replaceChildren();empty.hidden=list.runs.length>0;
  for(const r of list.runs){
   const tr=node('tr');
   const time=node('td');const b=node('button',new Date(r.started_at*1000).toLocaleTimeString());b.type='button';b.dataset.run=r.run_id;
   b.setAttribute('aria-pressed',String(r.run_id===selected));b.addEventListener('click',()=>show(r.run_id));time.append(b);
   tr.append(time,node('td',r.session_label||'—'),node('td',r.case_name||r.case_id||'—'),node('td',r.kind==='fictional'?'Fictional example':'Real'),
    node('td',String(r.status||'—').replace(/_/g,' ')),node('td',duration(r.duration_ms)));
   rows.append(tr);
  }
  status.textContent=list.runs.length+(list.runs.length===1?' run':' runs')+'. '+list.scope;
 }catch(_){status.textContent='The run list could not be loaded.';}
}
document.getElementById('refresh').addEventListener('click',load);
load();
