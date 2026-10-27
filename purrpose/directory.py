"""Historical directory candidates through AWS Zetaris, then bounded website reads.

No model is used; directory membership is never a trust/need decision.
"""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,build_opener
from uuid import uuid4
from .zetaris import read_config,preflight,DRIVER,error_category,SOURCE_URL
from .public_reader import NoRedirect,ReadFailure
from .safe_web import normalize_url
from .url_discovery import inspect_url
from .organization_live import organization_gaps
from .memory import MemoryUnavailable

TABLE='DONATION_FEASIBILITY_20261022.ontario_animal_directory'
SQL=('SELECT fact.BN, fact.`Legal Name`, fact.`Account Name`, fact.City, fact.Province, fact.Category, result.total '
     'FROM '+TABLE+' LATERAL VIEW explode(result.records) AS fact')
WEB_RESOURCE='e3567bb5-5d98-44d0-b0e8-9cdd3732c9e4'
API='https://open.canada.ca/data/api/action/datastore_search'
CAT_NAME=re.compile(r'\b(?:cats?|kittens?|feline)\b',re.I)
SOCIAL=('facebook.com','instagram.com','youtube.com','youtu.be','tiktok.com','x.com','twitter.com')


def select_candidates(rows,city=None,limit=3):
    unique={};conflicts=set();invalid=0;totals=[]
    for row in rows:
        if not isinstance(row,(list,tuple)) or len(row)!=7:
            invalid+=1;continue
        bn,name,account,town,province,category=(str(v).strip() if v is not None else '' for v in row[:6])
        if not re.fullmatch(r'\d{9}RR\d{4}',bn) or not name or len(name)>500 or len(account)>500 or len(town)>100 or province!='ON' or category.zfill(4)!='0180':
            invalid+=1;continue
        try:totals.append(int(row[6]))
        except (ValueError,TypeError):invalid+=1;continue
        record={'organization_number':bn,'organization_full_name':name,'account_name':account,
                'reported_city':town,'reported_province':province,'reporting_year':2024,
                'identity_source':SOURCE_URL,'current_registration_verified':False,'qualified':False,
                'remaining_minor':None,'website_status':'not_checked','needs_verified':False}
        if bn in unique and unique[bn]!=record:conflicts.add(bn)
        unique[bn]=record
    all_records=[v for k,v in unique.items() if k not in conflicts]
    cats=[r for r in all_records if CAT_NAME.search(r['organization_full_name']+' '+r['account_name'])]
    if city:cats=[r for r in cats if r['reported_city'].casefold()==city.casefold()]
    cats.sort(key=lambda r:(r['reported_city'].casefold(),r['organization_full_name'].casefold(),r['organization_number']))
    return cats[:limit],{'rows_observed':len(rows),'valid_unique_ontario_animals':len(all_records),
        'matching_cat_name_records':len(cats),'source_reported_total':max(totals) if totals else None,
        'invalid_rows':invalid,'conflicting_identifiers':len(conflicts),
        'coverage':'Historical2024 source; cat-related names only, not every rescue that may help cats.',
        'source_read_capped':len(rows)>=1000 or bool(totals and max(totals)>len(rows))}


def government_web_address(bn,reader=None):
    if not re.fullmatch(r'\d{9}RR\d{4}',bn):raise ReadFailure('invalid_charity_number')
    url=API+'?'+urlencode({'resource_id':WEB_RESOURCE,'filters':json.dumps({'BN/NE':bn}),
                           'fields':'BN/NE,Contact URL','limit':3})
    if reader:
        data=reader(url)
    else:
        with build_opener(NoRedirect).open(Request(url,headers={'User-Agent':'PurrposeResearch/0.1','Accept-Encoding':'identity'}),timeout=5) as response:
            raw=response.read(65537)
            if len(raw)>65536:raise ReadFailure('government_response_too_large')
            data=json.loads(raw)
    if not isinstance(data,dict) or data.get('success') is not True:raise ReadFailure('government_address_unavailable')
    records=data.get('result',{}).get('records')
    if not isinstance(records,list) or len(records)>3:raise ReadFailure('government_address_shape')
    addresses={r.get('Contact URL','').strip() for r in records if r.get('BN/NE')==bn and isinstance(r.get('Contact URL'),str) and r['Contact URL'].strip()}
    if len(addresses)!=1:raise ReadFailure('no_unique_historical_website')
    reported=addresses.pop()
    if '://' not in reported:target='https://'+reported
    elif reported.lower().startswith('http://'):target='https://'+reported[7:]
    else:target=reported
    target=normalize_url(target)
    hostname=urlsplit(target).hostname
    if any(hostname==s or hostname.endswith('.'+s) for s in SOCIAL):raise ReadFailure('social_platform_not_supported')
    return {'reported_website':reported,'website_url':target,'website_source':url,
            'website_basis':'CRA2024 reported contact URL, transported over HTTPS on the same host; current ownership not verified.'}


def government_web_directory(records,reader=None):
    identifiers=[r['organization_number'] for r in records]
    if not identifiers or len(identifiers)>100 or any(not re.fullmatch(r'\d{9}RR\d{4}',n) for n in identifiers):
        raise ReadFailure('bounded_charity_numbers_required')
    url=API+'?'+urlencode({'resource_id':WEB_RESOURCE,'filters':json.dumps({'BN/NE':identifiers}),
                          'fields':'BN/NE,Contact URL','limit':500})
    if reader:data=reader(url)
    else:
        with build_opener(NoRedirect).open(Request(url,headers={'User-Agent':'PurrposeResearch/0.1','Accept-Encoding':'identity'}),timeout=5) as response:
            raw=response.read(262145)
            if len(raw)>262144:raise ReadFailure('government_address_directory_too_large')
            data=json.loads(raw)
    if not isinstance(data,dict) or data.get('success') is not True:raise ReadFailure('government_address_unavailable')
    result=data.get('result',{});rows=result.get('records')
    if not isinstance(rows,list) or len(rows)>500 or int(result.get('total',len(rows)))>len(rows):raise ReadFailure('government_address_directory_incomplete')
    found={};pending=[]
    for record in records:
        bn=record['organization_number']
        try:
            address=government_web_address(bn,lambda ignored:{'success':True,'result':{'records':[r for r in rows if r.get('BN/NE')==bn]}})
            address['website_source']=url
            found[bn]=address
        except ReadFailure as exc:
            pending.append({**record,'website_status':'historical_contact_unavailable','website_error':str(exc)})
    return found,pending,url


def emit(result):
    print('DIRECTORY_RESULT:'+json.dumps(result,ensure_ascii=True),flush=True)


def query_rows(config,jvm):
    check=preflight(config,jvm)
    if not check['ready']:raise ReadFailure('jdbc_preflight_failed')
    import jpype,jaydebeapi
    if not jpype.isJVMStarted():jpype.startJVM(jvm,classpath=[config['ZETARIS_JDBC_JAR']],convertStrings=True)
    conn=jaydebeapi.connect(DRIVER,config['ZETARIS_JDBC_URL'],[config['ZETARIS_USERNAME'],config['ZETARIS_PASSWORD']],config['ZETARIS_JDBC_JAR'])
    try:
        cur=conn.cursor()
        try:
            cur.execute(SQL);return [[str(v) if v is not None else None for v in row] for row in cur.fetchmany(1001)]
        finally:cur.close()
    finally:conn.close()


def worker(env_file,jvm,city=None,query_only=False):
    result={'status':'directory_unavailable','mode':'directory_then_public_websites','observed_at':datetime.now(timezone.utc).isoformat(),
            'city':city,'candidates':[],'qualified':False,'remaining_minor':None,'tools':[],
            'source':SOURCE_URL,'reporting_year':2024,
            'limits':['Up to3 historical directory candidates, sorted city then full legal name. No trust ranking.',
                      'Cat-related names are a search filter, not proof of cat services, current need or authenticity.',
                      'Office city is historical organization location, not animal treatment location.',
                      'Historical contact URLs are not current website ownership verification.',
                      'No model calls or qualified recommendations; unavailable sources remain unknown.']}
    began=time.monotonic()
    try:
        rows=query_rows(read_config(env_file),jvm)
        candidates,summary=select_candidates(rows,city,limit=100)
        result.update(status='candidates_found' if candidates else 'no_directory_match',candidates=candidates[:3],directory_summary=summary)
        result['tools'].append({'tool':'zetaris','operation':'ontario_historical_directory','status':'completed',
                               'duration_ms':round((time.monotonic()-began)*1000),'row_count':len(rows)})
        emit(result)
    except Exception as exc:
        category=str(exc) if isinstance(exc,ReadFailure) else error_category(exc)
        result.update(error=category)
        result['tools'].append({'tool':'zetaris','operation':'ontario_historical_directory','status':'failed',
                               'duration_ms':round((time.monotonic()-began)*1000),'error_category':category})
        emit(result);return result
    if query_only:return result
    if not candidates:return result
    contact_began=time.monotonic()
    try:
        addresses,pending,address_source=government_web_directory(candidates)
        eligible=[r for r in candidates if r['organization_number'] in addresses]
        result['pending_website_candidates']=pending[:3]
        result['directory_summary'].update(historical_contact_eligible=len(eligible),historical_contact_unavailable=len(pending),
            selection='Same minimum public-contact criterion, then city and legal name; no trust/popularity score.')
        result['candidates']=eligible[:3] if eligible else pending[:3]
        result['tools'].append({'tool':'web','operation':'official_historical_contact_directory','status':'ok',
            'duration_ms':round((time.monotonic()-contact_began)*1000),'url':address_source})
        for record in result['candidates']:
            if record['organization_number'] in addresses:record.update(addresses[record['organization_number']])
        emit(result)
    except Exception as exc:
        result['contact_directory_error']=str(exc) if isinstance(exc,ReadFailure) else 'historical_contact_directory_failed'
        result['tools'].append({'tool':'web','operation':'official_historical_contact_directory','status':'failed',
            'duration_ms':round((time.monotonic()-contact_began)*1000),'error_category':result['contact_directory_error']})
        result['status']='directory_only_contact_unavailable';emit(result);return result
    for record in result['candidates']:
        if not record.get('website_url'):continue
        record['website_status']='reading_public_pages';emit(result)
        read=inspect_url(record['website_url'])
        read['organization_review']=organization_gaps(read)
        record['website_review']=read
        record['website_status']=read['status']
        for request in read.get('requests',[]):
            result['tools'].append({'tool':'web','operation':request['stage'],'status':'ok' if request['status']=='read' else 'failed',
                'duration_ms':request.get('duration_ms',0),'url':request['url'],'error_category':request.get('error')})
        emit(result)
    if result['candidates']:result['status']='candidate_checks_completed'
    emit(result);return result


def directory_case_id(city):
    """H-MEM scope for one directory search; scopes allow only letters, digits, '_' and '-'."""
    return 'DIRECTORY-ON-'+(re.sub(r'[^A-Z0-9]+','-',city.upper()).strip('-') if city else 'ALL')


class AWSDirectory:
    def __init__(self,registry,runner=None):self.registry=registry;self.runner=runner or subprocess.run
    def find(self,city=None,memory=None):
        if not all(hasattr(self.registry,k) for k in ('env_file','python','jvm')):
            return {'status':'directory_unavailable','error':'aws_jdbc_directory_not_configured','candidates':[],'qualified':False,'tools':[],'memory':{'status':'not_configured'}}
        command=[self.registry.python,'-m','purrpose.directory','--worker','--env-file',str(Path(self.registry.env_file).resolve()),'--jvm',str(Path(self.registry.jvm).resolve())]
        if city:command+=['--city',city]
        expired=False
        try:
            run=self.runner(command,cwd=str(Path(__file__).resolve().parents[1]),capture_output=True,text=True,encoding='utf-8',timeout=45)
            stdout=run.stdout
        except subprocess.TimeoutExpired as exc:
            expired=True;stdout=exc.stdout or ''
            if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
        except Exception:stdout=''
        lines=[s.split(':',1)[1] for s in stdout.splitlines() if s.startswith('DIRECTORY_RESULT:')]
        try:result=json.loads(lines[-1])
        except (IndexError,ValueError):result={'status':'directory_unavailable','error':'directory_worker_failed_or_deadline','candidates':[],'tools':[]}
        if expired:
            result.update(status='partial_before_deadline',error='45_second_budget_reached_no_automatic_retry')
            for r in result.get('candidates',[]):
                if r['website_status'] in ('checking_historical_address','reading_public_pages','not_checked'):r['website_status']='not_completed_before_deadline'
        result.update(qualified=False,remaining_minor=None,memory={'status':'not_configured'})
        started=time.monotonic()
        if memory and result.get('directory_summary'):
            case=directory_case_id(city)
            try:
                refs=[SOURCE_URL]+[c['website_source'] for c in result['candidates'] if c.get('website_source')]
                saved=memory.call('save',case,{'schema_version':1,'case_id':case,'run_id':str(uuid4()),
                   'scenario_type':'real_public_observations','organization':'Historical Ontario cat-name directory candidates',
                   'case_name':'Bounded candidate search','source_refs':refs,
                   'review_summary':{'qualified':False,'disposition':'pending_evidence'},'directory_observations':deepcopy(result)})
                result['memory']={'status':'saved','memory_id':saved['memory_id']}
            except (MemoryUnavailable,KeyError):result['memory']={'status':'save_failed'}
        result['tools'].append({'tool':'hmem','operation':'save','status':'ok' if result['memory']['status']=='saved' else 'failed' if result['memory']['status']=='save_failed' else 'not_used',
            'duration_ms':round((time.monotonic()-started)*1000),'memory_id':result['memory'].get('memory_id')})
        return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--env-file',required=True);p.add_argument('--jvm',required=True);p.add_argument('--city');p.add_argument('--query-only',action='store_true');a=p.parse_args()
    worker(a.env_file,a.jvm,a.city,a.query_only)
