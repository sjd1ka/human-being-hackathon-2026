import json
from unittest import TestCase
from .runs import RunStore


def review(roles, **extra):
    trace = [{'role': role, 'action': action, 'at_ms': i*10} for i, (role, action) in enumerate(roles)]
    return {'case_id': 'REAL-LUCY-GHS', 'case_name': 'Lucy', 'status': 'pending_evidence',
            'scenario_type': 'real_public_observations', 'trace': trace, **extra}


FULL = [('coordinator', 'start_review'), ('identity_risk', 'inspect_saved_official_observation'),
        ('evaluator', 'request_chronology_resolution'), ('dispute_resolver', 'resolve_dated_progression')]


class RunStoreTests(TestCase):
    def add(self, store, data, kind='real'):
        return store.add(data, kind=kind, started_at=1000.0, ended_at=1000.5, tools=[])

    def test_add_normalizes_roles_to_agents(self):
        store = RunStore()
        run = store.get(self.add(store, review(FULL)))
        self.assertEqual([s['agent'] for s in run['steps']], ['orchestrator', 'collector', 'evaluator', 'resolver'])
        self.assertEqual([s['seq'] for s in run['steps']], [1, 2, 3, 4])
        self.assertEqual(run['steps'][1]['role'], 'identity_risk')
        self.assertEqual(run['duration_ms'], 500)
        self.assertEqual([a['agent'] for a in run['agents']], ['orchestrator', 'collector', 'evaluator', 'resolver'])
        self.assertEqual(run['agents'][3]['decision'], 'resolve dated progression')
        self.assertEqual(run['agents'][3]['label'], 'Dispute Resolver')

    def test_skipped_agent_reported_with_reason(self):
        store = RunStore()
        run = store.get(self.add(store, review(FULL[:3])))
        resolver = run['agents'][3]
        self.assertIs(resolver['ran'], False)
        self.assertEqual(resolver['skipped_reason'], 'not needed in this run')
        self.assertIsNone(resolver['decision'])
        skip = review([('coordinator', 'plan')])
        skip['trace'].append({'role': 'coordinator', 'action': 'skip_role', 'at_ms': 5,
                              'skipped_role': 'rescue_need', 'reason': 'Required facts already validated'})
        collector = store.get(self.add(store, skip))['agents'][1]
        self.assertIs(collector['ran'], False)
        self.assertEqual(collector['skipped_reason'], 'Required facts already validated')
        skip['trace'].append({'role': 'identity_risk', 'action': 'read', 'at_ms': 6})
        collector = store.get(self.add(store, skip))['agents'][1]
        self.assertIs(collector['ran'], True)
        self.assertIsNone(collector['skipped_reason'])

    def test_cap_drops_oldest_and_missing_id_is_status(self):
        store = RunStore(cap=50)
        ids = [self.add(store, review(FULL)) for _ in range(51)]
        summaries = store.summaries()
        self.assertEqual(len(summaries), 50)
        self.assertEqual(summaries[0]['run_id'], ids[-1])
        self.assertEqual(summaries[-1]['run_id'], ids[1])
        self.assertEqual(store.get(ids[0]), {'status': 'run_not_found', 'run_id': ids[0]})

    def test_no_tokens_on_agents(self):
        store = RunStore()
        run = store.get(self.add(store, review(FULL, usage={'total_tokens': 9})))
        self.assertNotIn('token', json.dumps(run['agents']))

    def test_kind_kept_separate(self):
        store = RunStore()
        real = self.add(store, review(FULL))
        fictional = self.add(store, review(FULL, scenario_type='synthetic', case_id='SYN-MAPLE'), kind='fictional')
        by_id = {s['run_id']: s for s in store.summaries()}
        self.assertEqual(by_id[real]['kind'], 'real')
        self.assertEqual(by_id[fictional]['kind'], 'fictional')
        self.assertEqual(store.get(real)['scenario_type'], 'real_public_observations')
        self.assertEqual(store.get(fictional)['scenario_type'], 'synthetic')

    def test_reuses_run_id_tags_session_and_returns_copies(self):
        store = RunStore()
        run_id = self.add(store, review(FULL, run_id='abc'))
        self.assertEqual(run_id, 'abc')
        store.tag_session('abc', '0123456789abcdef')
        self.assertEqual(store.summaries()[0]['session_label'], '01234567')
        store.get('abc')['steps'].clear()
        self.assertEqual(len(store.get('abc')['steps']), 4)
        with self.assertRaises(ValueError):
            store.add(review(FULL), kind='other', started_at=0, ended_at=0, tools=[])

    def test_synthetic_recorded_at_becomes_offset(self):
        store = RunStore()
        data = review([])
        data['trace'] = [{'role': 'coordinator', 'action': 'plan', 'recorded_at': '1970-01-01T00:16:40.200000+00:00',
                          'sequence': 1, 'run_id': 'x', 'task_id': 'x:1', 'reason': 'Assign checks'}]
        step = store.get(self.add(store, data))['steps'][0]
        self.assertEqual(step['at_ms'], 200)
        self.assertEqual(step['details'], {'reason': 'Assign checks'})
