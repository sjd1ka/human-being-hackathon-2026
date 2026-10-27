"""Explicit bounded candidate discovery; directory membership is not approval."""
from copy import deepcopy
import re
from .chat_intent import ONTARIO_CITIES
from .directory import directory_case_id
from .everyday_intent import normalize,discovery_signal,organization_signal
import time
from .memory import MemoryUnavailable
from .workflow_runs import record_memory_read


def handle(app,state,message,zh):
    text=normalize(message)
    def reply(en,cn,**extra):
        return {'reply':cn if zh else en,'mode':'public_directory_discovery','new_cloud_calls':0,**extra}
    configured=not hasattr(app,'registry') or all(hasattr(app.registry,k) for k in ('env_file','python','jvm'))
    animal_request,organization_request=discovery_signal(text)
    requested=animal_request and (configured or organization_request)
    if any(w in text for w in ("don't",'do not','不要','别搜','别找')):
        state.pop('pending_directory',None)
        return None
    if 'lucy' in text or 'fictional' in text or '虚构' in text:return None
    if state.get('tool_context')=='directory' and any(w in text for w in ('history','历史','记忆记录')):
        directory=state.get('directory_result',{})
        city=directory.get('city')
        case=directory_case_id(city)
        started=time.time();status='not_configured';history={'status':'history_unavailable','entries':[]}
        if app.memory:
            try:
                history=app.memory.call('recall',case);status='ok'
            except MemoryUnavailable:status='failed';history={'status':'history_unavailable','entries':[]}
        record_memory_read(app,case,history,started,status)
        return reply('This is the saved directory investigation history, including its website observations. No new SQL query or website read was performed.' if status=='ok' else
                     'The saved investigation history could not be retrieved. No new SQL query or website read was performed.',
                     '这是保存的目录调查历史，包含当时的网站观察；没有重新查询 SQL 或访问网站。' if status=='ok' else '暂时无法取回调查历史；没有重新查询 SQL 或访问网站。',
                     workflow_history=history)
    if state.get('tool_context')=='directory':
        choices=state.get('directory_result',{}).get('candidates',[])
        selected=[c for c in choices if c['organization_full_name'].casefold() in text]
        if len(selected)==1:
            candidate=selected[0]
            read=candidate.get('website_review')
            if read:
                from .live_chat import result_reply
                state.update(public_read=deepcopy(read),public_url=candidate['website_url'],
                             public_audience='supporter',tool_context='website')
                app.turn['reused_read']=True
                result=result_reply(read,'supporter',zh,retained=True)
                result['selected_organization']=candidate['organization_full_name']
                return result
            return reply('This candidate has no completed website read. Share its public appeal link to investigate it. No new request was made.',
                         '这家候选还没有可用的网站读取结果。请提供公开案例链接继续检查；本次没有新请求。')
    if organization_signal(text):
        state.pop('pending_directory',None)
        state['awaiting_organization_url']=True
        return reply('Please share your organization’s public website or appeal link. I can check the readable pages and identify missing public information. Saying you represent it does not verify ownership.',
                     '请给我你们组织的公开官网或募款链接。我可以检查可读取的页面，列出缺失的信息；自称组织身份不代表已核实所有权。')
    if organization_request and not animal_request and configured:
        return reply('Are you looking for cat rescue organizations to support? Which Ontario city, or Ontario-wide?',
                     '你是在找可以支持的猫救助组织吗？希望查安省哪个城市，还是整个安省？')
    city=next((c for c in ONTARIO_CITIES if re.search(r'(?<!\w)'+re.escape(c.casefold())+r'(?!\w)',text)),None)
    cities=[c for c in ONTARIO_CITIES if re.search(r'(?<!\w)'+re.escape(c.casefold())+r'(?!\w)',text)]
    region=bool(re.search(r'\bontario\b',text)) or any(w in text for w in ('安省','安大略'))
    if (requested or state.get('pending_directory')) and len(cities)>1:
        return reply('Please choose one city or an Ontario-wide search. I have not searched yet.','请选一个城市，或查整个安省。目前没有搜索。')
    if requested and not city and not region and any(w in text for w in ('near me','nearby','附近','这里')):
        state['pending_directory']=True
        return reply('I do not know your location. Which Ontario city should I search?','我不知道你的位置。你希望查安省哪个城市？')
    pending=state.get('pending_directory',False)
    if pending and text in ('anywhere','any city','any is fine','都可以','哪里都行'):region=True
    if requested or (pending and (city or region)):
        if not city and not region:
            state['pending_directory']=True
            return reply('Which Ontario city should I search, or would you prefer Ontario-wide?','你希望查安省哪个城市，还是整个安省？')
        state.pop('pending_directory',None)
        result=app.dispatch('/api/find-organizations',{'city':city})
        state.update(directory_result=deepcopy(result),tool_context='directory',research=False,active=False)
        if result.get('error')=='aws_jdbc_directory_not_configured':
            return reply('The Zetaris directory connection is not configured on this server, so no directory query or website read was made. '
                         'This says nothing about which rescues exist. Ask about Lucy, or share a rescue’s public website to review it.',
                         '本服务器未配置 Zetaris 目录连接，因此没有执行目录查询或网站读取。这不代表当地没有救助组织。可以问 Lucy，或提供救助机构的公开网站进行检查。')
        if not result.get('candidates'):
            return reply('I could not return matching candidates from this bounded directory check. This does not mean no rescues exist. No automatic expansion was performed.',
                         '这次限定范围的目录检查没有返回匹配候选，不代表当地没有救助组织；没有自动扩大范围。',directory_result=result)
        return reply('I found historical directory candidates and checked available public websites. These are research leads, not verified trustworthy recommendations. Current needs and remaining funding are not yet verified.',
                     '找到了历史目录候选，并检查了可用的公开网站。这些是待核实线索，还不是可信推荐；当前需求和缺款仍待核实。',directory_result=result)
    if state.get('tool_context')=='directory' and (any(w in text for w in ('evidence','missing','reliable','trust','how much','证据','缺','可信','sources','source','safe','legit','money','funding','靠谱吗','钱','来源'))):
        return reply('These saved observations do not yet establish current registration, a specific medical need, or remaining funding. Open a candidate website to investigate a particular appeal. No new search was performed.',
                     '已有记录尚不能确认当前登记、具体医疗需求或缺款金额。可以提供某个候选的公开案例链接继续检查。本次没有重新搜索。',directory_result=deepcopy(state['directory_result']),retained_source_read=True)
    if configured and (state.get('tool_context')=='directory' or state.get('pending_directory')):
        return reply('I am not sure which action you mean. Are you choosing a city, asking about a listed organization, or sharing a public website? I have not performed a new search.',
                     '我不确定你想做哪一步：选择城市、追问某家组织，还是提供公开网站？本次没有重新搜索。')
    return None
