/* Review tab: a pure view model built only from backend chat fields, plus a textContent-only renderer. */
(function(root) {
  'use strict';
  const STATUS={ready:'Information available',needed:'More information needed',unable:'Unable to assess'};
  const REPORTED='Reported by the rescue',CONFIRMED='Confirmed';
  const money=minor=>'CAD '+(minor/100).toFixed(2);
  const amount=minor=>typeof minor==='number'?money(minor):'Not stated';
  const lowerFirst=t=>t.charAt(0).toLowerCase()+t.slice(1);
  const clean=t=>String(t).replace(/[.\s]+$/,'');
  const section=(name,status,items)=>({name,status,items});

  function fundingItems(figures,confirmed,notice){
    const label=confirmed?CONFIRMED:REPORTED;
    const row=(name,minor)=>typeof minor==='number'?{text:name+': '+money(minor),detail:label}:{text:name+': Not stated'};
    const items=[row('Target',figures.target),row('Raised',figures.raised),row('Remaining',figures.remaining)];
    if(notice)items.push({text:notice});
    return items;
  }

  function realCase(result,live){
    const d=result.research;
    const gate=name=>(d.gates||[]).find(g=>g.gate===name);
    const confirmedFunding=!!gate('funding_evidence')&&['established','passed'].includes(gate('funding_evidence').status);
    const form=d.external_form_observation||{},identity=d.official_identity_observation||{};
    const needed=STATUS.needed;
    const identityItems=[];
    if(identity.legal_name)identityItems.push({text:identity.legal_name+(identity.registration_number?' · '+identity.registration_number:''),
      detail:'Saved manual observation of the CRA listing ('+(identity.status_displayed||'status not recorded')+', observed '+(identity.observed_on||'date not recorded')+'); not a live registry check.',
      source_url:identity.source_url});
    if(gate('identity_geography'))identityItems.push({text:gate('identity_geography').explanation});
    const claims=[];
    for(const s of d.sources||[])claims.push({text:s.reported_state,detail:s.publisher+' · published '+s.published_on+' · '+String(s.kind).replace(/_/g,' '),source_url:s.url});
    if(gate('medical_need'))claims.push({text:'What remains unverified: '+gate('medical_need').explanation});
    if(d.independent_medical_verification===false)claims.push({text:'No independent medical confirmation is available yet.'});
    const funding=fundingItems({target:form.case_cost_minor,raised:form.raised_minor,remaining:form.remaining_minor},confirmedFunding);
    if(form.allocation_reported)funding.push({text:'Published use of surplus donations: '+form.allocation_reported,detail:REPORTED});
    const questions=(d.next_evidence||[]).map(t=>({text:'Could you share: '+lowerFirst(clean(t))+'?'}));
    let explanation='Saved research observed on '+(d.source_observed_on||'an earlier date')+'. The case is pending verification; this is not a qualified recommendation.';
    if(live&&live.status!=='read_complete')explanation+=' Your last source refresh did not complete, so the saved findings are not confirmed current.';
    return {kind:'case',title:d.organization_display_name+' — '+d.case_name,status:needed,explanation,fictional:false,
      sections:[section('Organization identity',needed,identityItems),section('Claims and evidence',needed,claims),
        section('Funding',needed,funding),section('Questions to ask the rescue',needed,questions)]};
  }

  function fictionalCase(c){
    const ready=c.qualified===true;
    const status=ready?STATUS.ready:STATUS.needed;
    const value=field=>{const e=(c.evidence||[]).find(x=>x.field===field);return e&&typeof e.value==='number'?e.value:null;};
    const claims=(c.evidence||[]).map(e=>({text:e.field.replace(/_/g,' ')+': '+(e.value===null?'Not stated':String(e.value)),
      detail:e.publisher+' · '+e.source_date+' · fictional source '+e.reference}));
    const identity=[{text:c.organization_full_name},{text:c.registration_category}];
    const questions=(c.unpassed_requirements||[]).map(t=>({text:'Could you share: '+lowerFirst(clean(t))+'?'}));
    if(!questions.length)questions.push({text:'No open questions in this fictional example.'});
    return {kind:'case',title:c.organization_full_name+' — '+c.case_name,status,fictional:true,
      explanation:ready?'Fictional example: every check passes for this made-up case. It is not a real recommendation.'
        :'Fictional example: some checks have not passed for this made-up case. It is not a real recommendation.',
      sections:[section('Organization identity',status,identity),section('Claims and evidence',status,claims),
        section('Funding',status,fundingItems({target:value('cost_minor'),raised:value('raised_minor'),remaining:c.remaining_minor},false,c.funding_notice)),
        section('Questions to ask the rescue',status,questions)]};
  }

  function organization(review){
    const sections=(review.gap_checklist||[]).map(g=>section(g.what_to_add,STATUS.needed,[
      {text:g.why},{text:g.where_to_obtain_or_publish,detail:g.responsible_party?'Action for: '+g.responsible_party:undefined}]));
    return {kind:'organization',title:review.organization_full_name,status:STATUS.needed,explanation:review.message||'',fictional:false,
      sections,privacy_note:review.privacy_note,guarantee:review.guarantee};
  }

  function buildReviewModel(result) {
    if(!result||typeof result!=='object')return null;
    if(result.organization_review)return organization(result.organization_review);
    if(result.research)return realCase(result,result.live_read);
    const groups=result.results&&['qualified','pending','no_current_gap'].map(k=>result.results[k]||[]);
    const first=groups&&groups.flat()[0];
    if(first)return first.scenario_type==='synthetic'?fictionalCase(first):null;
    if(result.live_read&&result.live_read.status!=='read_complete')
      return {kind:'case',title:'Source check',status:STATUS.unable,fictional:false,
        explanation:'The requested source check did not complete and no saved research is available, so nothing can be assessed.',sections:[]};
    return null;
  }

  function renderReview(container,model,{link}={}) {
    const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    container.replaceChildren();
    if(model.fictional)container.append(el('p','Fictional example','fictional-label'));
    const tone=status=>status===STATUS.ready?' is-ready':status===STATUS.unable?' is-unable':' is-needed';
    container.append(el('h3',model.title),el('p',model.status,'review-status review-overall'+tone(model.status)),el('p',model.explanation,'review-summary'));
    for(const s of model.sections){
      const box=el('div',undefined,'review-section');
      const head=el('div',undefined,'review-head');head.append(el('h4',s.name),el('p',s.status,'review-status'+tone(s.status)));
      box.append(head);
      const list=el('ul');
      for(const item of s.items){
        const li=el('li',item.text);
        if(item.detail)li.append(el('span',item.detail,'result'));
        if(item.source_url&&link)link(li,'Open source',item.source_url);
        list.append(li);
      }
      box.append(list);container.append(box);
    }
    if(model.privacy_note)container.append(el('p',model.privacy_note,'map-note'));
    if(model.guarantee)container.append(el('p',model.guarantee,'map-note'));
  }
  const api={buildReviewModel,renderReview,STATUS};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else Object.assign(root,api);
})(globalThis);
