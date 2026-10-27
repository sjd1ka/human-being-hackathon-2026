"""Execution records for explicit public-source and registry operations."""
from copy import deepcopy
import time
from uuid import uuid4
from .organization_live import organization_gaps
from .site_discovery import remember_discovery


def record_discovery(app, result, started):
    read_ended=time.time()
    result['organization_review']=organization_gaps(result)
    review_ended=time.time()
    trace=[{'role':'coordinator','action':'select_explicit_public_source_check','at_ms':0,
            'source_scope':result.get('entry_url'),'not_an_identity_check':True}]
    tools=[]
    for request in result.get('requests',[]):
        tools.append({'tool':'web','operation':request['stage'],'status':'ok' if request['status']=='read' else 'failed',
            'duration_ms':request.get('duration_ms',0),'url':request['url'],'error_category':request.get('error')})
    trace.append({'role':'rescue_need','action':'read_bounded_public_pages' if result.get('requests') else 'stop_before_public_read',
        'at_ms':max(0,round((read_ended-started)*1000)),'requests':deepcopy(result.get('requests',[])),
        'read_status':result['status'],'stop_reason':result.get('error'),'admission':deepcopy(result.get('admission'))})
    trace.append({'role':'evaluator','action':'identify_scoped_wording_and_gaps' if result['organization_review']['pages_read'] else 'unable_to_assess_unread_materials',
        'at_ms':max(0,round((review_ended-started)*1000)),'pages_read':result['organization_review']['pages_read'],
        'qualified':False,'remaining_minor':None,'credibility_check_complete':False})
    memory_began=time.monotonic()
    result=remember_discovery(result,app.memory)
    mem=result['memory'];status='ok' if mem['status']=='saved' else 'not_configured' if mem['status']=='not_configured' else 'failed'
    # A blocked URL with no request was deliberately not sent to the memory engine.
    if app.memory and not result.get('requests'):status='not_used'
    tools.append({'tool':'hmem','operation':'save','status':status,'duration_ms':round((time.monotonic()-memory_began)*1000),
                  'memory_id':mem.get('memory_id')})
    trace.append({'role':'coordinator','action':'record_source_observations' if mem['status']=='saved' else 'disclose_memory_status',
        'at_ms':max(0,round((time.time()-started)*1000)),'memory_status':mem['status'],'memory_id':mem.get('memory_id')})
    result['tools']=tools
    review={'run_id':str(uuid4()),'case_id':'SITE-'+result.get('site_id','BLOCKED').upper(),
        'case_name':result.get('organization','Blocked public URL'),'scenario_type':'bounded_public_source_review',
        'status':result['status'],'trace':trace}
    result['run_id']=app.runs.add(review,kind='real',started_at=started,ended_at=time.time(),tools=tools)
    app.turn['run_id']=result['run_id']
    return result


def record_registry(app,result,started):
    trace=[{'role':'coordinator','action':'select_fixed_registry_lookup','at_ms':0,'case_id':result['case_id']},
        {'role':'identity_risk','action':'query_historical_identity','at_ms':round((time.time()-started)*1000),
         'status':result['status'],'historical_year':2024,'error_category':result.get('error_category')},
        {'role':'evaluator','action':'retain_current_status_and_case_uncertainty','at_ms':round((time.time()-started)*1000),
         'current_registration_verified':False,'qualified':False}]
    review={'run_id':str(uuid4()),'case_id':result['case_id'],'case_name':'Historical registry — '+
        (result.get('identity',{}).get('organization_full_name') or result.get('organization_full_name') or result['case_id']),
        'scenario_type':'historical_registry_lookup','status':result['status'],'trace':trace}
    result['run_id']=app.runs.add(review,kind='real',started_at=started,ended_at=time.time(),tools=result.get('tools',[]))
    app.turn['run_id']=result['run_id']
    return result


def record_memory_read(app,case_id,result,started,status):
    tools=[{'tool':'hmem','operation':'recall','status':status,'duration_ms':round((time.time()-started)*1000),
            'memory_id':result.get('entries',[{}])[0].get('memory_id') if result.get('entries') else None}]
    review={'case_id':case_id,'case_name':'Retained source history','scenario_type':'source_memory_recall','status':'retained_history',
            'trace':[{'role':'coordinator','action':'read_scoped_history_without_source_refresh','at_ms':0,'case_id':case_id}]}
    run_id=app.runs.add(review,kind='real',started_at=started,ended_at=time.time(),tools=tools)
    app.turn['run_id']=run_id
    return run_id


def record_directory(app,result,started):
    if result.get('error')=='aws_jdbc_directory_not_configured':
        # Nothing was queried or read: record only the stop, never collector or evaluator work.
        reason='Zetaris directory not configured on this server'
        trace=[*({'role':'coordinator','action':'skip_role','skipped_role':role,'reason':reason,'at_ms':0}
                 for role in ('identity_risk','evaluator','dispute_resolver')),
               {'role':'coordinator','action':'stop_directory_not_configured','at_ms':0,'error_category':result['error']}]
        result['tools']=[{'tool':'zetaris','operation':'directory_query','status':'not_configured','duration_ms':0,'memory_id':None}]
        review={'case_id':'DIRECTORY-ON','case_name':'Ontario public directory discovery','scenario_type':'historical_directory_and_live_websites',
                'status':result['status'],'trace':trace}
        result['run_id']=app.runs.add(review,kind='real',started_at=started,ended_at=time.time(),tools=result['tools'])
        app.turn['run_id']=result['run_id']
        return result
    trace=[{'role':'coordinator','action':'select_bounded_directory_then_public_websites','at_ms':0},
           {'role':'identity_risk','action':'query_historical_directory_not_current_registration','at_ms':0},
           {'role':'rescue_need','action':'inspect_available_public_websites','at_ms':round((time.time()-started)*1000)},
           {'role':'evaluator','action':'retain_unverified_need_and_unknown_funding','qualified':False,'at_ms':round((time.time()-started)*1000)}]
    review={'case_id':'DIRECTORY-ON','case_name':'Ontario public directory discovery','scenario_type':'historical_directory_and_live_websites','status':result['status'],'trace':trace}
    result['run_id']=app.runs.add(review,kind='real',started_at=started,ended_at=time.time(),tools=result.get('tools',[]))
    app.turn['run_id']=result['run_id']
    return result
