/* Same-origin local-demo client. No credentials, automatic retry or provider calls. */
(function(root) {
  'use strict';
  class PurrposeApiError extends Error {
    constructor(code, status=0) {super(code); this.code=code; this.status=status;}
  }
  function createPurrposeClient({fetchImpl=root.fetch.bind(root), timeoutMs=65000}={}) {
    if (!Number.isInteger(timeoutMs) || timeoutMs<1 || timeoutMs>120000) throw Error('invalid_timeout');
    async function request(path, body) {
      const controller=new AbortController();
      const timer=setTimeout(()=>controller.abort(),timeoutMs);
      try {
        const response=await fetchImpl(path,{method:body===undefined?'GET':'POST',
          headers:body===undefined?{}:{'Content-Type':'application/json','X-Purrpose-Local':'1'},
          body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal,
          credentials:'same-origin',cache:'no-store'});
        let value;
        try {value=await response.json();} catch (_) {throw new PurrposeApiError('invalid_response',response.status);}
        if (!response.ok) throw new PurrposeApiError(value.error||'request_failed',response.status);
        return value;
      } catch (error) {
        if (error instanceof PurrposeApiError) throw error;
        throw new PurrposeApiError(controller.signal.aborted?'timeout_result_unknown':'network_result_unknown');
      } finally {clearTimeout(timer);}
    }
    return Object.freeze({
      status:()=>request('/api/status'),
      supporter:(preferences={})=>request('/api/supporter',preferences),
      organization:(publicLinks)=>request('/api/organization',{public_links:publicLinks}),
      chat:(sessionId,message)=>request('/api/chat',{session_id:sessionId,message}),
      feedback:(data)=>request('/api/feedback',data),
      history:(cutoff=null)=>request('/api/history',{cutoff}),
      demoUpdate:(action,requestId)=>request('/api/update',{action,request_id:requestId}),
      debug:()=>request('/api/debug',{}),
      runs:()=>request('/api/runs',{}),
      run:(runId)=>request('/api/runs/get',{run_id:runId})
    });
  }
  if(typeof module!=='undefined' && module.exports) module.exports={createPurrposeClient,PurrposeApiError};
  else root.createPurrposeClient=createPurrposeClient;
})(globalThis);
