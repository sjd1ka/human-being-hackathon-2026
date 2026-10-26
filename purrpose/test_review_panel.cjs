const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {buildReviewModel,STATUS}=require('./web/review-panel.js');
const samples=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures','chat-samples.json'),'utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
const text=model=>JSON.stringify(model);
const find=(model,name)=>model.sections.find(s=>s.name===name);

assert.deepEqual(STATUS,{ready:'Information available',needed:'More information needed',unable:'Unable to assess'});

// Lucy: more information needed, four sections in order, remaining not stated
let m=buildReviewModel(samples.lucy);
assert.equal(m.kind,'case');
assert.equal(m.status,'More information needed');
assert.equal(m.fictional,false);
assert.match(m.title,/Guelph Humane Society/);
assert.deepEqual(m.sections.map(s=>s.name),['Organization identity','Claims and evidence','Funding','Questions to ask the rescue']);
const funding=find(m,'Funding');
const remaining=funding.items.find(i=>/^Remaining/.test(i.text));
assert.match(remaining.text,/Not stated/);
assert.ok(!/\b0(\.00)?\b/.test(remaining.text));
for(const label of ['Target','Raised'])assert.match(funding.items.find(i=>i.text.startsWith(label)).text,/Not stated/);
assert.ok(find(m,'Claims and evidence').items.some(i=>/^https:\/\/guelphhumane\.ca\//.test(i.source_url||'')));
assert.ok(find(m,'Questions to ask the rescue').items.length>0);
assert.ok(find(m,'Questions to ask the rescue').items.every(i=>/^Could you share/.test(i.text)));
assert.ok(find(m,'Organization identity').items.some(i=>/119236305RR0001/.test(i.text)));

// reported vs confirmed funding labels
let reported=clone(samples.lucy);
reported.research.external_form_observation.raised_minor=50000;
let f=find(buildReviewModel(reported),'Funding').items.find(i=>i.text.startsWith('Raised'));
assert.match(f.text,/CAD 500\.00/);assert.match(f.detail,/Reported by the rescue/);
const confirmed=clone(reported);
confirmed.research.gates=confirmed.research.gates.map(g=>g.gate==='funding_evidence'?{...g,status:'established'}:g);
f=find(buildReviewModel(confirmed),'Funding').items.find(i=>i.text.startsWith('Raised'));
assert.match(f.detail,/Confirmed/);

// fictional qualified case
m=buildReviewModel(samples.fictional_qualified);
assert.equal(m.status,'Information available');
assert.equal(m.fictional,true);
assert.match(m.explanation,/[Ff]ictional/);
assert.match(find(m,'Funding').items.find(i=>/^Remaining/.test(i.text)).text,/CAD 1000\.00/);
// a fictional case that has not qualified never reads as available
m=buildReviewModel(samples.fictional_pending);
assert.equal(m.status,'More information needed');assert.equal(m.fictional,true);
assert.match(find(m,'Funding').items.find(i=>/^Remaining/.test(i.text)).text,/Not stated/);

// real case never reads as available even if a field claims it
let tampered=clone(samples.lucy);tampered.research.qualified=true;
assert.equal(buildReviewModel(tampered).status,'More information needed');

// incomplete live read: saved research exists, so more information needed plus a plain caveat
m=buildReviewModel(samples.lucy_incomplete_refresh);
assert.equal(m.status,'More information needed');
assert.match(m.explanation,/did not complete/);
// incomplete live read and no saved research
m=buildReviewModel({reply:'x',live_read:{status:'read_incomplete',sources:[],stage:'robots',error:'network_or_timeout'}});
assert.equal(m.status,'Unable to assess');
// a complete read without saved research is still not an assessment
assert.equal(buildReviewModel({reply:'x',live_read:{status:'read_complete',sources:[]}}),null);

// organization request
m=buildReviewModel(samples.organization);
assert.equal(m.kind,'organization');
assert.equal(m.sections.length,samples.organization.organization_review.gap_checklist.length);
assert.equal(m.privacy_note,samples.organization.organization_review.privacy_note);
assert.equal(m.guarantee,samples.organization.organization_review.guarantee);
assert.equal(m.status,'More information needed');

// no case content
assert.equal(buildReviewModel({reply:'Hi!'}),null);
assert.equal(buildReviewModel(null),null);
assert.equal(buildReviewModel({reply:'x',results:{status:'needs_preference',qualified:[],pending:[],no_current_gap:[]}}),null);

// language: missing information is never worded as a negative finding
for(const key of Object.keys(samples)){
  const model=buildReviewModel(samples[key]);
  if(!model)continue;
  assert.ok(!/fraud|fake|scam|failed check/i.test(text(model)),key+' uses negative-finding wording');
  for(const s of model.sections)assert.ok(Object.values(STATUS).includes(s.status),key+' section status '+s.status);
}

// hostile text stays a literal string
tampered=clone(samples.lucy);tampered.research.sources[0].reported_state='<script>x</script>';
assert.ok(text(buildReviewModel(tampered)).includes('<script>x</script>'));

console.log('Review model: statuses, section order, funding labels and Not stated, fictional label, organization checklist, no-content null and neutral wording checks passed.');
