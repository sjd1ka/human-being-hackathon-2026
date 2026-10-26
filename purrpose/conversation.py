"""Bilingual chat: optional validated model intent, then bounded code matching.

With a configured model, every ordinary message is classified by the model;
the validated intent becomes a canonical phrase and code writes the reply.
Safety refusals, negations, two-city ambiguity and explicit source refreshes
stay code-only. Without a model, or when it fails, bounded matching is used
and labelled as such.
"""
import re
from .journeys import public_record
from .research_case import assess_saved_research
from .organization_research import organization_research, LINKS as REAL_LINKS
from .model_intent import ModelIntent
from .chat_intent import ONTARIO_CITIES

GUARDS = ('ignore instructions', 'ignore previous', '忽略规则', '转账', 'pay for me', 'donate for me', '替我捐')
NEGATIONS = ("don't", 'do not', 'not ottawa', 'not toronto', '不要', '不想', '不是')
REFRESH = ('refresh', 'recheck website', 'check website again', '重新检查官网', '重新读取', '刷新官网')
FICTIONAL = ('synthetic', 'fictional', '虚构', '模拟')  # Only literal words may switch to fictional cases.
CITY_ALIASES = {'Ottawa': ('渥太华',), 'Toronto': ('多伦多',)}
LIST_WORDS = ('list of', 'which rescues', 'what rescues', 'all rescues', 'all the rescues', 'organizations in',
              'organisations in', 'charities in', 'shelters in', 'trusted organizations', 'trusted rescues',
              '有哪些机构', '机构名单')
ABOUT_WORDS = ('what can you do', 'what do you do', 'how does this work', 'how does purrpose', 'what is purrpose',
               'how do you decide', 'who are you', '你能做什么', '怎么运作')
DONATE_WORDS = ('how do i donate', 'how to donate', 'where do i donate', 'where can i donate', 'how can i donate',
                'donate now', '怎么捐', '如何捐')
THANKS_WORDS = ('thank', 'bye', 'cheers', '谢谢', '再见')
CANONICAL = {'greet': 'hello', 'amount': 'how much', 'allocation': 'allocation', 'evidence': 'evidence',
             'gaps': 'missing', 'select_real_case': 'lucy', 'history': 'history',
             'organization_checklist': 'lucy organization checklist', 'confirm_expansion': 'yes',
             'list_organizations': 'list of organizations', 'about': 'what can you do',
             'donate_how': 'how do i donate', 'thanks': 'thank you'}


def cities_in(text):
    """Listed Ontario cities named in a casefolded message, in list order."""
    return [c for c in ONTARIO_CITIES
            if re.search(r'(?<![a-z])'+re.escape(c.casefold())+r'(?![a-z])', text)
            or any(a in text for a in CITY_ALIASES.get(c, ()))]


def canonical(proposal):
    """Phrase the bounded matcher already handles for a validated model intent."""
    name, city = proposal['intent'], proposal['city']
    if name in CANONICAL:
        return CANONICAL[name]
    place = 'find a cat in '+city.lower() if city else (
        'find a cat anywhere in ontario' if proposal['region_wide'] else 'i want to help a cat')
    return ('fictional ' if name == 'fictional_demo' else '')+place


def code_only(text):
    return any(any(w in text for w in group) for group in (GUARDS, NEGATIONS, REFRESH)) or len(cities_in(text)) > 1


def model_context(state, offer_ontario=False):
    return {'awaiting_expansion_answer': bool(state['expand'] or offer_ontario), 'real_case_selected': bool(state.get('research')),
            'fictional_mode': state.get('collection') == 'synthetic', 'fictional_case_active': bool(state['active'])}


class Conversation:
    def __init__(self, app, model=None):
        self.app = app
        self.sessions = {}
        self.model = ModelIntent(model) if model else None

    def reply(self, session_id, message):
        self.app.turn = {'run_id': None, 'reused_read': False}
        result = self.answer(session_id, message)
        turn = self.app.turn
        if turn['run_id']:
            self.app.runs.tag_session(turn['run_id'], session_id)
            note = 'New review run'
        elif turn['reused_read']:
            note = 'Reused a recent source read; no new run'
        else:
            note = 'Answered from saved results; no agents ran'
        result['agent_run'] = {'run_id': turn['run_id'], 'note': note, 'model': self.model_info(result)}
        return result

    def model_info(self, result):
        info = result.get('model_intent')
        if not info:
            return None
        calls = info.get('new_cloud_calls', 0)
        tokens = None
        if calls > 0:
            trace = getattr(getattr(self.model, 'provider', None), 'trace', None) or []
            usage = trace[-1].get('usage') if trace else None
            total = usage.get('total_tokens') if isinstance(usage, dict) else None
            tokens = total if type(total) is int else None
        return {'route': info.get('route'), 'status': info.get('status'), 'intent': info.get('intent'),
                'new_cloud_calls': calls, 'total_tokens': tokens}

    def answer(self, session_id, message):
        if (not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,80}', session_id)
                or not isinstance(message, str) or not 1 <= len(message.strip()) <= 1500):
            raise ValueError('Bounded session and message required')
        if session_id not in self.sessions:
            if len(self.sessions) >= 100:
                raise ValueError('Session capacity reached; restart the local demo')
            self.sessions[session_id] = {'city': None, 'region_wide': False, 'active': False, 'expand': False, 'collection': 'real'}
        state = self.sessions[session_id]
        text = message.strip().casefold()
        zh = bool(re.search(r'[\u4e00-\u9fff]', text))
        offer_ontario = state.pop('offer_ontario', False)  # An Ontario offer lasts for one reply only.
        if self.model is None or code_only(text):
            return self.match(state, text, zh)
        proposal, info = self.model.propose(message.strip(), model_context(state, offer_ontario))
        meta = {'model_intent': info, 'new_cloud_calls': info['new_cloud_calls']}
        if proposal is None:
            return self.match(state, text, zh, meta)  # Labelled bounded-matching fallback.
        if proposal['intent'] == 'outside_area':
            state['offer_ontario'] = True
            return {'reply': ('Purrpose 目前只覆盖安省，无法在那里查找。要看安省范围内的线索吗？' if zh else
                              'Purrpose only covers Ontario for now, so it cannot search there. Would you like to see leads anywhere in Ontario?'),
                    'mode': 'model_intent_validated', **meta}
        if proposal['intent'] == 'fictional_demo' and not any(w in text for w in FICTIONAL):
            # Like source refreshes, switching to made-up cases needs the user's explicit words.
            return {'reply': ('你想看安省的真实线索，还是虚构演示案例？请说“安省都可以”或“虚构演示”。' if zh else
                              'Do you want real Ontario leads or the fictional demo case? Say "anywhere in Ontario" for real leads, or "fictional demo" for the made-up example.'),
                    'mode': 'model_intent_validated', **meta}
        if proposal['intent'] == 'confirm_expansion' and offer_ontario:
            return self.match(state, 'find a cat anywhere in ontario', zh, meta, 'model_intent_validated')
        if proposal['intent'] == 'clarify':
            return {'reply': ('能再具体一点吗？我可以帮你找想支持的小猫（渥太华、多伦多或安省都可以），或解释案例的证据、金额和来源。'
                              if zh else "Could you say a bit more? I can help you find a cat to support (Ottawa, Toronto or anywhere in Ontario), or explain a case's evidence, amounts and sources."),
                    'mode': 'model_intent_validated', **meta}
        if proposal['intent'] == 'organization_checklist' and not state.get('research'):
            # A stated rescue role is not identity, and must not open another organization's case.
            return {'reply': ('这个原型只评估已配置的 Lucy 公开页面，不会审查你的机构，自称的身份也不代表已核实。'
                              '请打开“For rescues”机构演示，或说“Lucy organization checklist”查看示例清单。' if zh else
                              'This prototype only assesses the configured Lucy public pages, so it has not reviewed your '
                              'organization, and saying you run a rescue does not verify who you are. Open the "For rescues" '
                              'walkthrough, or say "Lucy organization checklist" to see an example checklist.'),
                    'mode': 'model_intent_validated', **meta}
        return self.match(state, canonical(proposal), zh, meta, 'model_intent_validated')

    def match(self, state, text, zh, meta=None, mode='bounded_intent_matching'):
        def response(en, cn, **extra):
            return {'reply': cn if zh else en, 'mode': mode, 'new_cloud_calls': 0, **(meta or {}), **extra}
        if any(x in text for x in GUARDS):
            return response('I can explain public evidence, but cannot change verification rules or handle payments.',
                            '我可以解释公开证据，但不能修改核查规则或代收、代付捐款。')
        if text in ('hi', 'hello', 'hey', '你好', '您好'):
            state['greeted'] = state.get('greeted', 0)+1
            if state['greeted'] > 1:
                return response("Hi again! You can ask about Lucy's case, look for a cat by Ontario city, or ask what Purrpose can do.",
                                '又见面了！你可以问 Lucy 的案例、按安省城市找小猫，或者问 Purrpose 能做什么。')
            return response('Hi! I can help find a case, explain missing evidence, amounts and sources. Which Ontario city, or anywhere in Ontario?',
                            '你好！我可以帮你找案例，解释缺失证据、金额和来源。想看安省哪个城市，还是安省都可以？')
        if any(w in text for w in NEGATIONS):
            return response('Please state the city you do want, or say “anywhere in Ontario”. I have not changed your selection.',
                            '请直接告诉我你想看的城市，或说“安省都可以”。我没有更改选择。')
        if len(text) <= 30 and any(w in text for w in THANKS_WORDS):
            return response("You're welcome. Ask any time about a case, its sources or what is still missing.",
                            '不客气。随时可以问案例、来源或仍缺少的信息。')
        if any(w in text for w in ABOUT_WORDS):
            return response('Purrpose checks the evidence behind an animal rescue appeal. When you ask about a case, four agent roles in code '
                            'read its permitted sources, check what they support, look into conflicting statements and keep anything unproven '
                            'marked as missing. An AI model only works out what you are asking; code writes every answer, and nothing counts as '
                            'verified without a source. There is one real case right now, Lucy from Guelph Humane Society, plus a labelled '
                            'fictional example.',
                            'Purrpose 检查动物救助呼吁背后的证据。你问到某个案例时，四个代码角色会读取允许的来源、核对来源支持什么、调查相互矛盾的说法，'
                            '并把未经证实的内容标为缺失。AI 模型只负责理解你在问什么；每个回答都由代码写出，没有来源就不算核实。'
                            '目前有一个真实案例：Guelph Humane Society 的 Lucy，另有一个标明为虚构的示例。')
        if any(w in text for w in DONATE_WORDS):
            return response("Purrpose does not take payments or donations. Give through the rescue's own official website or charity page, "
                            "after checking its registration and the case's evidence. For Lucy, the donation link is on Guelph Humane "
                            'Society’s own appeal page; ask “What evidence is missing?” first to see what is still unverified.',
                            'Purrpose 不收款，也不代收捐款。请在核对机构登记和案例证据后，通过救助机构自己的官网或慈善页面捐款。'
                            'Lucy 的捐款链接在 Guelph Humane Society 自己的呼吁页面上；可以先问“还缺哪些证据？”了解哪些内容尚未核实。')
        if any(w in text for w in LIST_WORDS):
            return response('Purrpose cannot call any rescue trusted: it reviews the evidence behind one appeal at a time. A list of '
                            'Ontario animal charities from the CRA’s 2024 charity data is planned through the Zetaris connection, '
                            'which is not connected yet. Right now one real case can be reviewed: Lucy, from Guelph Humane Society. '
                            'Say “Tell me about Lucy” to see its evidence.',
                            'Purrpose 不能称任何救助机构“可信”，它一次只审查一个呼吁背后的证据。基于加拿大税务局 2024 年慈善数据的'
                            '安省动物慈善机构名单计划通过 Zetaris 提供，目前尚未接通。现在可以审查一个真实案例：Guelph Humane Society 的 Lucy。'
                            '说“Tell me about Lucy”查看证据。')
        select_research = any(w in text for w in ('lucy', 'real case', '真实案例'))
        research_history = any(w in text for w in ('history', '历史记录', '审查记录'))
        if research_history and not select_research and state.get('collection') == 'synthetic':
            history = self.app.dispatch('/api/history', {})
            return response('This is the latest retained review of the fictional case, not a new check. '+history.get('message', ''),
                            '这是虚构案例最近保存的审查记录，不是重新检查。', history=history)
        select_research = select_research or (research_history and not state.get('research'))
        if any(w in text for w in FICTIONAL):
            state.update(collection='synthetic', research=False, active=False, expand=False)
            state.pop('last_live_read', None)
        if select_research:
            state['collection'] = 'real'
        organization_request = any(w in text for w in ('organization checklist', 'our rescue', 'as a rescue', '我们的机构', '机构需要补', '组织要补'))
        refresh = any(w in text for w in REFRESH)
        research_question = any(w in text for w in ('how much', 'remaining', '还缺', '多少钱', 'allocation', '分配', '用途', 'money', '查到', 'found', 'verified', 'trust', '可信', 'missing', '缺', 'source', '来源', 'evidence', '证据', '登记', 'registered', 'latest', '最新', '补充', 'provide'))
        if select_research or (state.get('research') and (research_question or refresh or research_history or organization_request)):
            state.update(research=True, active=False, expand=False)
            dossier = assess_saved_research()
            if organization_request:
                checklist = organization_research(sorted(REAL_LINKS), self.app.real_latest_run)
                return response('Here is the Lucy public-information checklist. Organization actions and unfinished system checks are separate. No private documents or fresh retrieval are involved.',
                                '这是 Lucy 的公开材料清单，已区分机构可补充的内容和系统尚未完成的检查。请在自己的公开渠道更新，不要在此上传私密资料。',
                                organization_review=checklist)
            if research_history:
                history = self.app.dispatch('/api/research/history', {})
                return response('This is the latest retained Lucy review, not a fresh source check. '+history.get('message',''),
                                '这是最近保存的 Lucy 审查记录，不是重新联网检查。'+('未配置记忆或无可用记录。' if history['status']=='history_unavailable' else ''),
                                research_history=history)
            if refresh:
                read = self.app.dispatch('/api/research/read', {})
                state['last_live_read'] = read
                complete = read.get('status') == 'read_complete'
                en = ('Both configured articles were retrieved.' if complete else 'The requested source check did not fully complete.')
                cn = '已读取两篇指定文章。' if complete else '本次来源检查未完整完成。'
                return response(en+' '+('This is a recent cached attempt, not a new fetch. ' if read.get('cached') else '')+
                                'This checks only those articles, not every possible update. Medical, funding and risk remain unverified; remaining need is unknown. The identity and allocation observations below are saved manual research, not refreshed by this request.',
                                cn+('本次复用了近期读取记录，并非再次联网。' if read.get('cached') else '')+
                                '只检查这两篇文章，不能保证没有其他更新。医疗、资金和风险仍待核实，剩余需求未知。下方身份及资金用途信息仍是人工保存的记录，本次没有更新。',
                                research=dossier, live_read=read)
            last_read = state.get('last_live_read')
            if any(w in text for w in ('how much', 'remaining', '还缺多少钱', '多少钱')):
                en='The remaining amount is unknown: no validated case cost and raised total are available. Gift options are not a funding gap.'
                cn='剩余需求未知：尚未核实这项案例的费用和已筹总额。捐款选项不是资金缺口。'
            elif any(w in text for w in ('allocation', '分配', '用途', 'money')):
                en='The linked form states that donations beyond care costs support other GHS animals. We have not independently verified actual spending or recipient settlement ownership.'
                cn='官网链接的表单说明：超过照护费用的捐款会用于 GHS 的其他动物。实际支出和最终收款归属尚未独立核实。'
            elif any(w in text for w in ('missing', '缺', '补充', 'provide')):
                en='Still needed: current corresponding clinical material, actual treatment location, same-case costs and funding/allocation, recipient verification and required risk checks.'
                cn='仍需：当前对应医疗材料、实际治疗地点、案例费用和资金分配、收款归属及规定的风险检查。请在适当公开渠道补充，不要向此 demo 上传私密资料。'
            else:
                en='Saved research: the organization reports Lucy gave birth to three kittens. A manual CRA review found the registered organization; case medical/funding and risk checks remain incomplete. This is a pending lead, not a qualified recommendation.'
                cn='已保存的调查显示：机构报道 Lucy 生下三只小猫，人工查阅 CRA 找到了登记记录。但案例医疗、资金和风险核查仍不完整，这是待核实线索，不是合格推荐。'
            if last_read and last_read.get('status') != 'read_complete':
                en += ' Your last requested refresh was incomplete; the saved findings are not confirmed current.'
                cn += ' 你上次请求的刷新未完整完成；保存的调查不能视为当前已确认的信息。'
            return response(en+' These findings were observed on 24 October 2026; this chat did not fetch sources again. Say “refresh Lucy” to check the two configured articles.',
                            cn+' 这些资料查阅于2026年10月24日；本次对话没有重新联网读取。', research=dossier)
        named = cities_in(text)
        if len(named) > 1:
            return response('Please choose one city, or anywhere in Ontario.', '请选择一个城市，或安省都可以。')
        city = named[0] if named else None
        broad = any(w in text for w in ('anywhere in ontario', 'all ontario', 'in ontario', '安省都可以', '整个安省', '在安省')) and city is None
        yes = text in ('yes', 'yes please', '可以', '好', '是的')
        discovery = any(w in text for w in ('help a cat', 'find a cat', 'find a rescue', 'want to donate', '帮助小猫', '帮助一只', '想捐', '找救助'))
        discovery = discovery or bool(re.search(r'\b(find|help|support|donate)\b.*\b(cats?|kittens?|rescues?)\b', text))
        # A region mention alone is not consent to search or expand.
        broad = broad and (discovery or text in ('anywhere in ontario', 'all ontario', 'ontario', '安省都可以', '整个安省', '在安省'))
        if city or broad or discovery or (yes and state['expand']):
            state['research'] = False
            state.pop('last_live_read', None)
            if city:
                state.update(city=city, region_wide=False)
            elif broad:
                state.update(city=None, region_wide=True)
            result = self.app.dispatch('/api/supporter', {'city': state['city'], 'region_wide': state['region_wide'],
                                                        'allow_expansion': bool(yes and state['expand']),
                                                        'collection': state.get('collection', 'real')})
            state['expand'] = bool(result.get('expansion_question') or result.get('status') == 'no_city_match')
            state['active'] = any(result.get(k) for k in ('qualified', 'pending', 'no_current_gap'))
            if state.get('collection') == 'real' and state['active']:
                state.update(research=True, active=False)
            if yes and result.get('expanded'):
                state.update(city=None, region_wide=True)
            return response(result.get('question') or result['message'],
                            ('请选择安省城市，或说“安省都可以”。' if result['status'] == 'needs_preference'
                             else ('没有已确认治疗城市匹配的真实线索。是否查看安省范围、地点仍待核实的线索？' if result['status']=='no_city_match'
                                   else ('这是已保存的真实待核实线索，不是全网搜索，也不是合格推荐。' if state.get('collection')=='real'
                                         else '这是虚构案例演示，不是真实捐款推荐。'))), results=result)
        if any(w in text for w in ('how much', 'remaining', '还缺', '多少钱', 'why', 'unverified', 'missing', '为什么', '没核实', '未核实', '缺什么', 'source', 'evidence', '来源', '证据', 'latest', '最新',
                                   'allocation', 'money go', 'money used', '分配', '用途')):
            if not state['active']:
                return response('Which case? Ask about Lucy, or first look for a cat in an Ontario city or anywhere in Ontario.',
                                '你指哪个案例？请先说想看渥太华、多伦多，还是安省都可以。')
            # Always re-evaluate current case state; never answer from a stale chat copy.
            journeys = self.app.journeys()
            record = public_record(self.app.service.case, journeys.review(self.app.service.case))
            self.app.remember_run(journeys)
            amount = 'Not yet known' if record['remaining_minor'] is None else 'CAD '+format(record['remaining_minor']/100, '.2f')
            return response('Current simulated case: '+record['case_name']+'. Remaining disclosed need: '+amount+'. See the evidence and unresolved requirements below. Latest here means current fixture state, not a live website check.',
                            '当前模拟案例：'+record['case_name']+'。公开资料计算的剩余需求：'+amount+'。证据和未完成要求见下方。“最新”指当前模拟状态，并未访问真实网站。',
                            results={'status': 'results', 'message': record['funding_notice'],
                                     'qualified': [record] if record['qualified'] else [],
                                     'pending': [] if record['qualified'] or record['remaining_minor'] == 0 else [record],
                                     'no_current_gap': [record] if record['remaining_minor'] == 0 else []})
        return response('I did not confidently understand that. Try “I want to help a cat”, “Ottawa”, “How much is still needed?”, or “What evidence is missing?”. No new search or update was performed.',
                        '这句话我还不能可靠理解。可以试试“我想帮助一只猫”“渥太华”“还缺多少钱？”或“哪些证据未核实？”。这次没有执行新搜索或更新。')
