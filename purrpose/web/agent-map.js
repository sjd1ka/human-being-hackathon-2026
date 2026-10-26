/* Agent map: a pure view model built from backend run fields, plus a textContent-only renderer. */
(function(root) {
  'use strict';
  const FIXED_NOTE='Agents are code roles in one process. The AI model is used only where marked.';
  const ORDER=['orchestrator','collector','evaluator','resolver'];
  const LABEL={orchestrator:'Orchestrator',collector:'Evidence Collector',evaluator:'Evidence Evaluator',resolver:'Dispute Resolver'};
  const words=text=>String(text).replace(/_/g,' ');
  const sentence=text=>{const t=words(text);return t.charAt(0).toUpperCase()+t.slice(1);};
  const pluralCalls=n=>n+(n===1?' call':' calls');
  function elapsed(ms){return ms<1000?ms+' ms':(ms/1000).toFixed(1)+' s';}
  function span(agent){
    if(!agent.ran)return '';
    const steps=agent.step_count+(agent.step_count===1?' step':' steps');
    return agent.step_count>1?steps+' · '+(agent.duration_ms<1?'<1 ms':agent.duration_ms+' ms'):steps;
  }
  function value(v){
    if(v===null||v===undefined)return 'not stated';
    return typeof v==='string'?v:JSON.stringify(v);
  }
  function detailText(details){
    return Object.entries(details||{}).map(([k,v])=>words(k)+': '+value(v)).join('; ');
  }
  function nvidiaText(agentRun){
    const m=agentRun&&agentRun.model;
    if(m&&m.status==='failed')return 'NVIDIA Nemotron · call failed, answered with fixed phrases';
    if(m&&m.status==='invalid_output'){
      const tokens=typeof m.total_tokens==='number'?' · '+m.total_tokens+' tokens':'';
      return 'NVIDIA Nemotron · '+pluralCalls(m.new_cloud_calls||1)+tokens+" · answer didn't fit the supported requests, used fixed phrases";
    }
    if(m&&m.new_cloud_calls>0){
      const tokens=typeof m.total_tokens==='number'?m.total_tokens+' tokens':'tokens not reported';
      return 'NVIDIA Nemotron · '+pluralCalls(m.new_cloud_calls)+' · '+tokens;
    }
    return 'NVIDIA Nemotron · not used';
  }
  function hmemText(run){
    if(!run)return 'H-MEM · not used in this answer';
    const events=(run.tools||[]).filter(t=>t.tool==='hmem');
    if(!events.length)return 'H-MEM · not recorded for this run';
    if(events.length===1&&events[0].status==='not_configured')return 'H-MEM · not configured';
    const parts=events.map(t=>{
      const state=t.status==='ok'?'ok':t.status==='not_configured'?'not configured':'failed';
      return t.operation+' '+state+(t.status!=='not_configured'?' ('+t.duration_ms+' ms)':'')+(t.memory_id?' · '+t.memory_id:'');
    });
    return 'H-MEM · '+parts.join(' · ');
  }
  function buildMapModel(run,agentRun) {
    const tools=[{tool:'nvidia',text:nvidiaText(agentRun)},{tool:'hmem',text:hmemText(run)},
      {tool:'zetaris',text:'Zetaris · not connected yet'},{tool:'nightshift',text:'Nightshift · not connected'}];
    if(!run)return {header:(agentRun&&agentRun.note)||'No run for this answer',note:FIXED_NOTE,fictional:false,cards:[],tools,log:{}};
    const byAgent=Object.fromEntries((run.agents||[]).map(a=>[a.agent,a]));
    const cards=ORDER.map(key=>{
      const agent=byAgent[key]||{agent:key,label:LABEL[key],ran:false,step_count:0,duration_ms:0,decision:null,skipped_reason:'not needed in this run'};
      const warn=key==='evaluator'&&(run.steps||[]).some(s=>s.agent==='evaluator'&&/conflict|chronology/.test(s.action));
      return {agent:key,label:agent.label||LABEL[key],state:!agent.ran?'skipped':warn?'warn':'done',
        line:agent.ran?sentence(agent.decision||'ran'):'Skipped: '+(agent.skipped_reason||'not needed in this run'),
        duration:span(agent)};
    });
    const log=Object.fromEntries(ORDER.map(k=>[k,[]]));
    for(const s of run.steps||[]){
      (log[s.agent]||(log[s.agent]=[])).push({text:s.seq+'. '+s.role+' · '+words(s.action)+' (+'+s.at_ms+' ms)',result:detailText(s.details)});
    }
    const ranCount=cards.filter(c=>c.state!=='skipped').length;
    return {header:'Run · '+ranCount+(ranCount===1?' agent ran':' agents ran')+' · '+elapsed(run.duration_ms||0),
      note:FIXED_NOTE,fictional:run.kind==='fictional',cards,tools,log};
  }
  function renderAgentMap(container,model) {
    const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    container.replaceChildren();
    if(model.fictional)container.append(el('p','Fictional example','fictional-label'));
    container.append(el('h3',model.header,'map-header'));
    const logBox=el('div',undefined,'map-log');logBox.setAttribute('aria-live','polite');
    if(model.cards.length){
      const flow=el('ol',undefined,'map-cards');
      const buttons=[];
      for(const card of model.cards){
        const li=el('li');const b=el('button',undefined,'map-card state-'+card.state);b.type='button';b.setAttribute('aria-pressed','false');
        b.append(el('span',undefined,'dot'),el('strong',card.label),el('span',card.line,'line'),el('span',card.duration,'time'));
        b.addEventListener('click',()=>{
          for(const x of buttons)x.setAttribute('aria-pressed',String(x===b&&b.getAttribute('aria-pressed')!=='true'));
          logBox.replaceChildren();
          if(b.getAttribute('aria-pressed')!=='true')return;
          const rows=model.log[card.agent]||[];
          logBox.append(el('h4','Step log · '+card.label));
          if(!rows.length)logBox.append(el('p','No steps recorded: this agent did not run.'));
          const list=el('ul');
          for(const r of rows){const item=el('li',r.text);if(r.result)item.append(el('span',r.result,'result'));list.append(item);}
          logBox.append(list);
        });
        buttons.push(b);li.append(b);flow.append(li);
      }
      container.append(flow);
    }
    const toolList=el('ul',undefined,'map-tools');
    for(const t of model.tools){
      const used=!/not used|not connected|not configured|not recorded/.test(t.text);
      const failed=/failed|didn't fit/.test(t.text);
      toolList.append(el('li',t.text,failed?'tool-failed':used?'tool-used':'tool-idle'));
    }
    container.append(el('h4','Tools in this answer','map-subhead'),toolList,logBox,el('p',model.note,'map-note'));
  }
  const api={buildMapModel,renderAgentMap,FIXED_NOTE};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else Object.assign(root,api);
})(globalThis);
