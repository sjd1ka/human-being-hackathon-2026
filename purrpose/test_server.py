from http.client import HTTPConnection
from http.server import HTTPServer
import json
from threading import Thread
from unittest import TestCase, main

from .server import LocalApp, handler_for


class LocalServerTests(TestCase):
    def setUp(self):
        self.app = LocalApp()
        self.server = HTTPServer(('127.0.0.1', 0), handler_for(self.app))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, data=None, headers=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        h = {} if data is None else {'Content-Type': 'application/json', 'X-Purrpose-Local': '1'}
        h.update(headers or {})
        connection.request('GET' if data is None else 'POST', path,
                           body=None if data is None else json.dumps(data), headers=h)
        response = connection.getresponse()
        raw = response.read()
        status, mime = response.status, response.getheader('Content-Type')
        connection.close()
        return status, json.loads(raw) if mime.startswith('application/json') else raw.decode()

    def test_page_and_truthful_status(self):
        status, page = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('one real pending lead plus a separate fictional workflow', page)
        self.assertIn('No payments or qualified real recommendation', page)
        self.assertEqual(self.request('/api/status')[1]['nightshift'], 'not_connected')

    def test_real_research_is_distinct_from_fixture_qualification(self):
        status, page = self.request('/research.html')
        self.assertEqual(status, 200)
        self.assertIn('Remaining amount: unknown', page)
        self.assertIn('researched manually', page)
        self.assertIn('not a qualified donation recommendation', page)
        self.assertIsNone(self.app.latest_run)

    def test_connected_design_has_local_assets_and_honest_scope(self):
        status,page=self.request('/home.html')
        self.assertEqual(status,200)
        self.assertIn('one real pending case',page)
        self.assertNotIn('fonts.googleapis.com',page)
        self.assertNotIn('<script>',page)
        self.assertNotIn('Sign in',page)
        self.assertEqual(self.request('/design-home.js')[0],200)
        self.assertEqual(self.request('/agent-map.js')[0],200)
        self.assertEqual(self.request('/review-panel.js')[0],200)
        for name in ('/api-client.js','/agent-map.js','/review-panel.js','/design-home.js'):
            self.assertIn('src="'+name+'"',page)
        self.assertEqual(self.request('/design-home.css')[0],200)
        self.assertEqual(self.request('/design-favicon.svg')[0],200)

    def test_mentor_explanation_and_organization_walkthrough_are_explicit(self):
        status, page = self.request('/architecture.html')
        self.assertEqual(status, 200)
        self.assertIn('ONE SEPARATE LIVE TEST', page)
        self.assertIn('DEFERRED / NOT CONNECTED', page)
        self.assertNotIn('<script', page)
        self.assertEqual(self.request('/architecture.css')[0], 200)
        status, page = self.request('/organizations.html')
        self.assertEqual(status, 200)
        self.assertIn('Fictional organization walkthrough', page)
        self.assertIn('No website is fetched or changed', page)
        self.assertEqual(self.request('/organization-demo.js')[0], 200)

    def test_functional_update_cycle_uses_backend_not_canned_page(self):
        first = self.request('/api/supporter', {'city': 'Ottawa'})[1]
        self.assertIsNone(first['pending'][0]['remaining_minor'])
        updated = self.request('/api/update', {'action': 'clarify', 'request_id': 'one'})[1]
        self.assertTrue(updated['review']['qualified'])
        current = self.request('/api/supporter', {'city': 'Ottawa'})[1]
        self.assertEqual(current['qualified'][0]['remaining_minor'], 100000)
        failed = self.request('/api/update', {'action': 'source_outage', 'request_id': 'two'})[1]
        self.assertFalse(failed['review']['qualified'])

    def test_organization_and_history_without_fake_memory(self):
        r = self.request('/api/organization', {'public_links': ['https://example.invalid/purrpose/maple']})[1]
        self.assertEqual(r['status'], 'gap_review')
        self.assertTrue(r['gap_checklist'])
        history = self.request('/api/history', {})[1]
        self.assertEqual(history['status'], 'history_unavailable')

    def test_unknown_fields_and_arbitrary_actions_rejected(self):
        self.assertEqual(self.request('/api/supporter', {'sql': 'DROP TABLE x'})[0], 400)
        self.assertEqual(self.request('/api/update', {'action': 'call_paid_model', 'request_id': 'x'})[0], 400)

    def test_cross_origin_and_missing_local_header_rejected(self):
        self.assertEqual(self.request('/api/debug', {}, {'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.request('/api/debug', {}, {'X-Purrpose-Local': ''})[0], 403)

    def test_host_guard_and_no_filesystem_serving(self):
        self.assertEqual(self.request('/', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/../.env.local')[0], 404)

    def test_update_idempotency_rejects_different_action(self):
        self.request('/api/update', {'action': 'clarify', 'request_id': 'same'})
        duplicate = self.request('/api/update', {'action': 'clarify', 'request_id': 'same'})[1]
        self.assertTrue(duplicate['idempotent_replay'])
        self.assertEqual(self.request('/api/update', {'action': 'fully_funded', 'request_id': 'same'})[0], 400)

    def test_request_size_limit_and_no_paid_route(self):
        self.assertEqual(self.request('/api/supporter', {'city': 'x'*5000})[0], 413)
        self.assertEqual(self.request('/api/nvidia', {})[0], 400)

    def test_debug_is_explicit_and_default_user_result_has_no_trace(self):
        result = self.request('/api/supporter', {'city': 'Ottawa'})[1]
        self.assertNotIn('trace', str(result.keys()))
        debug = self.request('/api/debug', {})[1]
        self.assertTrue(debug['latest_run']['trace'])
        self.assertEqual(debug['new_cloud_calls'], 0)

    def test_runs_endpoints_list_and_get(self):
        run_id = self.app.runs.add({'case_id': 'REAL-LUCY-GHS', 'case_name': 'Lucy', 'status': 'pending_evidence',
                                    'scenario_type': 'real_public_observations',
                                    'trace': [{'role': 'coordinator', 'action': 'start_review', 'at_ms': 0}]},
                                   kind='real', started_at=1.0, ended_at=2.0, tools=[])
        listed = self.request('/api/runs', {})[1]
        self.assertEqual([r['run_id'] for r in listed['runs']], [run_id])
        self.assertIn('cleared on restart', listed['scope'])
        run = self.request('/api/runs/get', {'run_id': run_id})[1]
        self.assertEqual(run['steps'][0]['agent'], 'orchestrator')
        self.assertEqual(self.request('/api/runs/get', {'run_id': 'nope'})[1]['status'], 'run_not_found')

    def test_runs_endpoints_keep_request_guards(self):
        self.assertEqual(self.request('/api/runs', {}, {'X-Purrpose-Local': ''})[1], {'error': 'local_request_required'})
        self.assertEqual(self.request('/api/runs', {}, {'X-Purrpose-Local': ''})[0], 403)
        self.assertEqual(self.request('/api/runs', {'extra': 1})[0], 400)
        self.assertEqual(self.request('/api/runs/get', {'run_id': 5})[0], 400)
        self.assertEqual(self.request('/api/runs/get', {})[0], 400)

    def test_fictional_review_is_recorded_as_fictional_run(self):
        self.request('/api/supporter', {'city': 'Ottawa'})
        runs = self.request('/api/runs', {})[1]['runs']
        self.assertEqual([(r['kind'], r['scenario_type']) for r in runs], [('fictional', 'synthetic')])
        run = self.request('/api/runs/get', {'run_id': runs[0]['run_id']})[1]
        self.assertTrue(run['steps'])
        self.assertTrue(all(type(s['at_ms']) is int and s['at_ms'] >= 0 for s in run['steps']))

    def test_dashboard_page_served_with_local_assets(self):
        status, page = self.request('/dashboard.html')
        self.assertEqual(status, 200)
        for name in ('/api-client.js', '/agent-map.js', '/dashboard.js'):
            self.assertIn('src="'+name+'"', page)
        self.assertNotIn('<script>', page)
        self.assertNotIn('http://', page)
        self.assertNotIn('https://', page)
        self.assertNotIn('style=', page)
        self.assertIn('Runs since this server started; cleared on restart.', page)
        self.assertEqual(self.request('/dashboard.js')[0], 200)
        self.assertEqual(self.request('/dashboard.css')[0], 200)
        self.assertIn('/dashboard.html', self.request('/home.html')[1])


if __name__ == '__main__':
    main()
