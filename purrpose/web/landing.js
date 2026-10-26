'use strict';
/* Landing page: colour scheme, example chips and a plain GET hand-off to the app. No API calls here. */
const form=document.getElementById('prompt'),box=document.getElementById('appeal'),send=document.getElementById('send');
const picks=document.querySelectorAll('[data-pick]');
function scheme(value){const warm=value==='warm';document.documentElement.dataset.scheme=warm?'warm':'cool';for(const p of picks)p.setAttribute('aria-pressed',String(p.dataset.pick===(warm?'warm':'cool')));for(const id of ['fav-ico','fav-svg'])document.getElementById(id).href=warm?'/design-favicon-warm.svg':'/design-favicon.svg';try{localStorage.setItem('purrpose-scheme',warm?'warm':'cool');}catch(_){}}
for(const p of picks)p.addEventListener('click',()=>scheme(p.dataset.pick));
try{scheme(localStorage.getItem('purrpose-scheme')||'cool');}catch(_){scheme('cool');}
function sync(){send.disabled=!box.value.trim();box.style.height='auto';box.style.height=Math.min(box.scrollHeight,220)+'px';}
box.addEventListener('input',sync);
box.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();if(!send.disabled)form.requestSubmit();}});
for(const chip of document.querySelectorAll('[data-text]'))chip.addEventListener('click',()=>{box.value=chip.dataset.text;sync();box.focus();});
form.addEventListener('submit',e=>{if(!box.value.trim())e.preventDefault();});
sync();
