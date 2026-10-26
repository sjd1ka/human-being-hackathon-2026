"""Local functional demo. Serial requests, fixture sources; cloud model calls only when explicitly configured."""
import argparse
from copy import deepcopy
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time
from datetime import datetime
from pathlib import Path

from .__main__ import load_scenario
from .history import history_from_memory
from .journeys import Journeys
from .memory import HMem, MemoryUnavailable
from .updates import UpdateService
from .conversation import Conversation
from .research_case import assess_saved_research
from .public_reader import bounded_read
from .source_analysis import analyze_read
from .real_review import review_real_observations, CASE_ID as REAL_CASE_ID
from .organization_research import organization_research, LINKS as REAL_LINKS
from .real_discovery import discover_real
from .feedback import Feedback
from .provider import from_settings, read_settings
from .runs import RunStore

PUBLIC_LINK = 'https://example.invalid/purrpose/maple'
FUNDING_LINK = PUBLIC_LINK+'/funding'
WEB = Path(__file__).with_name('web')


class LocalApp:
    def __init__(self, memory=None, model=None):
        self.memory = memory
        self.model = model
        case = load_scenario('exhausted')
        case['public_links'] = [PUBLIC_LINK, FUNDING_LINK]
        self.pending_source = deepcopy(case['sources']['funding'])
        self.source_outage = False
        self.service = UpdateService(case, self.read_fixture, {FUNDING_LINK: 'funding'}, memory)
        self.latest_run = None
        self.requests = {}
        self.conversation = Conversation(self, model)
        self.feedback = Feedback(self.conversation)
        self.public_read_cache = None
        self.public_read_at = 0
        self.real_latest_run = None
        self.runs = RunStore()
        self.turn = {'run_id': None, 'reused_read': False}

    def read_fixture(self, url):
        if self.source_outage:
            raise TimeoutError('synthetic source outage')
        return deepcopy(self.pending_source)

    def status(self):
        return {'mode': 'local_real_research_and_synthetic_demo', 'source_review_date': '2026-10-24',
                'source_review_date_scope': 'frozen_synthetic_fixture_only',
                'default_ui_discovery': 'real_curated', 'runtime_roles': 'deterministic_code',
                'memory': 'real_local_reference_configured' if self.memory else 'not_configured',
                'nightshift': self.model.status()['nightshift'] if self.model else 'not_connected',
                'cloud_inference_in_this_server': bool(self.model and self.model.ready),
                'model_provider': self.model.status() if self.model else None,
                'public_web_fetching': 'two_fixed_articles_only', 'payments': False,
                'public_fixture_link': PUBLIC_LINK,
                'limitation': 'Restart resets simulated source contents; configured H-MEM history remains.'}

    def journeys(self):
        return Journeys([self.service.case], self.memory)

    def remember_run(self, journeys):
        if journeys.runs:
            self.latest_run = deepcopy(list(journeys.runs.values())[-1])
            self.service.last_review = deepcopy(self.latest_run)
            for review in journeys.runs.values():
                stamps = [datetime.fromisoformat(e['recorded_at']).timestamp()
                          for e in review.get('trace', []) if e.get('recorded_at')]
                started = min(stamps) if stamps else time.time()
                # Synthetic fixture runs: recorded_at stamps give real step offsets.
                self.turn['run_id'] = self.runs.add(review, kind='fictional', started_at=started,
                                                    ended_at=max(stamps) if stamps else started, tools=[])

    def dispatch(self, path, data):
        allowed = {'/api/supporter': {'city', 'region_wide', 'allow_expansion', 'collection'},
                   '/api/organization': {'public_links'}, '/api/update': {'action', 'request_id'},
                   '/api/history': {'cutoff'}, '/api/debug': set(),
                   '/api/chat': {'session_id', 'message'}, '/api/research': set(), '/api/research/read': set(),
                   '/api/research/history': {'cutoff'}, '/api/runs': set(), '/api/runs/get': {'run_id'},
                   '/api/feedback': {'session_id','request_id','kind','message','city'}}
        if path not in allowed:
            raise ValueError('Unknown operation')
        if not isinstance(data, dict) or set(data)-allowed[path]:
            raise ValueError('Unsupported request fields')
        if path == '/api/feedback':
            return self.feedback.submit(**data)
        if path == '/api/runs':
            return {'runs': self.runs.summaries(), 'scope': 'Runs since this server started; cleared on restart.'}
        if path == '/api/runs/get':
            if not isinstance(data.get('run_id'), str):
                raise ValueError('Run ID required')
            return self.runs.get(data['run_id'])
        if path == '/api/research':
            return assess_saved_research()
        if path == '/api/research/history':
            if not self.memory:
                return {'status': 'history_unavailable', 'message': 'Real H-MEM is not configured.'}
            return history_from_memory(self.memory, REAL_CASE_ID, data.get('cutoff'))
        if path == '/api/research/read':
            if self.public_read_cache is not None and time.monotonic()-self.public_read_at < 60:
                self.turn['reused_read'] = True
                return {**deepcopy(self.public_read_cache), 'cached': True}
            self.public_read_cache = bounded_read()
            self.public_read_cache['analysis'] = analyze_read(self.public_read_cache)
            started = time.time()
            self.real_latest_run = review_real_observations(self.public_read_cache, self.memory)
            run_id = self.runs.add(self.real_latest_run, kind='real', started_at=started, ended_at=time.time(),
                                   tools=self.real_latest_run.get('tools', []))
            self.turn['run_id'] = run_id
            self.public_read_cache['run_id'] = run_id
            self.public_read_cache['review'] = {k: deepcopy(v) for k, v in self.real_latest_run.items() if k != 'trace'}
            self.public_read_at = time.monotonic()
            return {**deepcopy(self.public_read_cache), 'cached': False}
        if path == '/api/chat':
            return self.conversation.reply(data.get('session_id'), data.get('message'))
        if path == '/api/supporter':
            data = dict(data)
            collection = data.pop('collection', 'synthetic')
            if collection not in ('real', 'synthetic'):
                raise ValueError('Unknown collection')
            for k in ('region_wide', 'allow_expansion'):
                if k in data and type(data[k]) is not bool:
                    raise ValueError('Preference flags must be boolean')
            if collection == 'real':
                return discover_real(**data)
            journeys = self.journeys()
            result = journeys.supporter(**data)
            self.remember_run(journeys)
            return result
        if path == '/api/organization':
            links = data.get('public_links')
            if isinstance(links, list) and links and all(isinstance(u, str) and u in REAL_LINKS for u in links):
                return organization_research(links, self.real_latest_run)
            journeys = self.journeys()
            result = journeys.organization(public_links=data.get('public_links'))
            self.remember_run(journeys)
            return result
        if path == '/api/history':
            if not self.memory:
                return {'status': 'history_unavailable', 'message': 'Configure real H-MEM to query retained reviews.'}
            return history_from_memory(self.memory, self.service.case['case_id'], data.get('cutoff'))
        if path == '/api/debug':
            return {'latest_run': self.latest_run, 'real_latest_run': self.real_latest_run, 'update_events': deepcopy(self.service.events),
                    'model_trace': deepcopy(getattr(self.model, 'trace', [])),
                    'new_cloud_calls': 0, 'scope': 'Explicit local demo debug view; not production authorization.'}
        action, request_id = data.get('action'), data.get('request_id')
        if action not in ('clarify', 'more_funds', 'fully_funded', 'source_outage'):
            raise ValueError('Choose a supported synthetic update')
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
            raise ValueError('Bounded request ID required')
        if request_id in self.requests:
            previous_action, result = self.requests[request_id]
            if action != previous_action:
                raise ValueError('Request ID already used for another action')
            return {**deepcopy(result), 'idempotent_replay': True}
        self.pending_source = deepcopy(load_scenario('complete')['sources']['funding'])
        self.source_outage = action == 'source_outage'
        if action == 'more_funds':
            self.pending_source['facts']['raised_minor'] = 120000
        elif action == 'fully_funded':
            self.pending_source['facts']['raised_minor'] = 200000
        result = self.service.notify(FUNDING_LINK, request_id=request_id, explicit_refresh=True)
        if result.get('review'):
            self.latest_run = deepcopy(result['review'])
        self.requests[request_id] = (action, deepcopy(result))
        return result


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def own_origin(self):
            return 'http://127.0.0.1:'+str(self.server.server_address[1])

        def valid_host(self):
            return self.headers.get('Host') == self.own_origin().removeprefix('http://')

        def respond(self, status, content, mime='application/json; charset=utf-8'):
            body = json.dumps(content).encode() if mime.startswith('application/json') else content
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, {'error': 'host_rejected'})
            if self.path == '/api/status':
                return self.respond(200, app.status())
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/home.html': ('design-home.html', 'text/html; charset=utf-8'),
                     '/organizations.html': ('organization-demo.html', 'text/html; charset=utf-8'),
                     '/architecture.html': ('architecture.html', 'text/html; charset=utf-8'),
                     '/architecture.css': ('architecture.css', 'text/css; charset=utf-8'),
                     '/organization-demo.js': ('organization-demo.js', 'text/javascript; charset=utf-8'),
                     '/design-home.css': ('design-home.css', 'text/css; charset=utf-8'),
                     '/design-home.js': ('design-home.js', 'text/javascript; charset=utf-8'),
                     '/design-favicon.svg': ('design-favicon.svg', 'image/svg+xml'),
                     '/design-favicon-warm.svg': ('design-favicon-warm.svg', 'image/svg+xml'),
                     '/research.html': ('research.html', 'text/html; charset=utf-8'),
                     '/research.js': ('research.js', 'text/javascript; charset=utf-8'),
                     '/agent-map.js': ('agent-map.js', 'text/javascript; charset=utf-8'),
                     '/api-client.js': ('api-client.js', 'text/javascript; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/app.css': ('app.css', 'text/css; charset=utf-8')}
            if self.path not in files:
                return self.respond(404, {'error': 'not_found'})
            filename, mime = files[self.path]
            self.respond(200, (WEB/filename).read_bytes(), mime)

        def do_POST(self):
            if (not self.valid_host() or self.headers.get('X-Purrpose-Local') != '1'
                    or self.headers.get('Origin', self.own_origin()) != self.own_origin()):
                return self.respond(403, {'error': 'local_request_required'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > 4096 or self.headers.get('Transfer-Encoding'):
                    return self.respond(413, {'error': 'body_limit'})
                if self.headers.get_content_type() != 'application/json':
                    return self.respond(415, {'error': 'json_required'})
                self.connection.settimeout(5)
                data = json.loads(self.rfile.read(length))
                result = app.dispatch(self.path, data)
                self.respond(200, result)
            except (ValueError, TypeError):
                self.respond(400, {'error': 'invalid_request'})
            except MemoryUnavailable:
                self.respond(503, {'error': 'memory_unavailable', 'message': 'No fallback pretending memory worked.'})
            except Exception:
                self.respond(500, {'error': 'operation_failed'})
    return Handler


def main():
    p = argparse.ArgumentParser(description='Local-only Purrpose functional demo; model calls only when explicitly configured')
    p.add_argument('--port', type=int, default=8766)
    p.add_argument('--reference', type=Path)
    p.add_argument('--state', type=Path)
    p.add_argument('--workspace', default='local-ui')
    p.add_argument('--env-file', type=Path, help='Local file with PURRPOSE_MODEL_* settings (never committed)')
    args = p.parse_args()
    if bool(args.reference) != bool(args.state):
        p.error('Supply both reference and state')
    memory = HMem(args.reference, args.state, workspace=args.workspace) if args.reference else None
    model = from_settings(read_settings(args.env_file, os.environ))
    app = LocalApp(memory, model)
    # Deliberately serial: the demo H-MEM file store has no concurrent-write guarantee.
    server = HTTPServer(('127.0.0.1', args.port), handler_for(app))
    print('Purrpose local demo: http://127.0.0.1:'+str(server.server_address[1]), flush=True)
    if model:
        status = model.status()
        print('Chat model:', status['route'], status['model'], 'ready' if model.ready else 'blocked: '+status['config_error'], flush=True)
        if status['route'] == 'meterless' and model.ready:
            print('Meterless discovery:', model.probe()['connection'], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
