"""Bounded in-process record of review runs; cleared on restart, never persisted."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4

AGENT_OF = {'coordinator': 'orchestrator', 'identity_risk': 'collector', 'rescue_need': 'collector',
            'funding_channel': 'collector', 'evaluator': 'evaluator', 'dispute_resolver': 'resolver'}
AGENT_LABEL = {'orchestrator': 'Orchestrator', 'collector': 'Evidence Collector',
               'evaluator': 'Evidence Evaluator', 'resolver': 'Dispute Resolver'}
NOT_NEEDED = 'not needed in this run'
STEP_META = {'role', 'action', 'at_ms', 'recorded_at', 'sequence', 'run_id', 'task_id',
             'plan_revision', 'state_version', 'decision_method'}


def step_offset_ms(entry, index, started_at):
    if isinstance(entry.get('at_ms'), int):
        return entry['at_ms']
    try:
        return max(0, round((datetime.fromisoformat(entry['recorded_at']).timestamp()-started_at)*1000))
    except (KeyError, TypeError, ValueError):
        return 0


class RunStore:
    def __init__(self, cap=50):
        self.cap = cap
        self.runs = []  # oldest first

    def add(self, review, *, kind, started_at, ended_at, tools):
        if kind not in ('real', 'fictional'):
            raise ValueError('Run kind must be real or fictional')
        run_id = review.get('run_id') or str(uuid4())
        steps = []
        for i, entry in enumerate(review.get('trace', [])):
            steps.append({'seq': i+1, 'role': entry['role'], 'agent': AGENT_OF.get(entry['role'], 'orchestrator'),
                          'action': entry['action'], 'at_ms': step_offset_ms(entry, i, started_at),
                          'details': {k: deepcopy(v) for k, v in entry.items() if k not in STEP_META}})
        run = {'run_id': run_id, 'kind': kind, 'scenario_type': review.get('scenario_type'),
               'case_id': review.get('case_id'), 'case_name': review.get('case_name') or review.get('case_id'),
               'status': review.get('status') or review.get('disposition'),
               'started_at': started_at, 'ended_at': ended_at,
               'duration_ms': max(0, round((ended_at-started_at)*1000)),
               'session_id': None, 'steps': steps, 'tools': deepcopy(tools),
               'agents': self.agents(review.get('trace', []), steps)}
        self.runs = [r for r in self.runs if r['run_id'] != run_id] + [run]
        del self.runs[:-self.cap]
        return run_id

    @staticmethod
    def agents(trace, steps):
        skipped = {}
        for entry in trace:
            if entry['action'] == 'skip_role' and entry['role'] == 'coordinator':
                agent = AGENT_OF.get(entry.get('skipped_role'))
                if agent:
                    skipped.setdefault(agent, entry.get('reason') or NOT_NEEDED)
        out = []
        for agent, label in AGENT_LABEL.items():
            mine = [s for s in steps if s['agent'] == agent]
            ran = bool(mine)
            duration = (mine[-1]['at_ms']-mine[0]['at_ms']) if ran else 0
            out.append({'agent': agent, 'label': label, 'ran': ran, 'step_count': len(mine),
                        'duration_ms': duration,
                        'decision': mine[-1]['action'].replace('_', ' ') if ran else None,
                        'skipped_reason': None if ran else skipped.get(agent, NOT_NEEDED)})
        return out

    def tag_session(self, run_id, session_id):
        for run in self.runs:
            if run['run_id'] == run_id:
                run['session_id'] = session_id

    def summaries(self):
        return [{'run_id': r['run_id'], 'kind': r['kind'], 'scenario_type': r['scenario_type'],
                 'case_id': r['case_id'], 'case_name': r['case_name'], 'status': r['status'],
                 'started_at': r['started_at'], 'duration_ms': r['duration_ms'],
                 'session_label': r['session_id'][:8] if r['session_id'] else None}
                for r in reversed(self.runs)]

    def get(self, run_id):
        for run in self.runs:
            if run['run_id'] == run_id:
                return deepcopy(run)
        return {'status': 'run_not_found', 'run_id': run_id}
