"""Bounded code-role review of real observations; no real qualification path."""
from copy import deepcopy
from datetime import datetime, timezone
import time
from uuid import uuid4
from .memory import MemoryUnavailable, fingerprint
from .research_case import assess_saved_research
from .source_analysis import analyze_read

CASE_ID = 'REAL-LUCY-GHS'
PROFILE = 'real-observation-review-v1'


def review_real_observations(read, memory=None):
    trace, tools = [], []
    start = time.monotonic()
    def elapsed_ms():
        return int((time.monotonic()-start)*1000)
    def event(role, action, **details):
        trace.append({'role': role, 'action': action, 'at_ms': elapsed_ms(), **details})
    dossier = assess_saved_research()
    prior = None
    memory_status = 'not_configured'
    if memory:
        began = time.monotonic()
        try:
            entries = memory.call('recall', CASE_ID)['entries']
            prior = next((e for e in entries if e['payload'].get('policy_profile') == PROFILE), None)
            memory_status = 'recalled'
        except MemoryUnavailable:
            memory_status = 'recall_failed'
        tools.append({'tool': 'hmem', 'operation': 'recall', 'status': 'failed' if memory_status == 'recall_failed' else 'ok',
                      'duration_ms': int((time.monotonic()-began)*1000), 'memory_id': prior['memory_id'] if prior else None})
    else:
        tools.append({'tool': 'hmem', 'operation': 'recall', 'status': 'not_configured', 'duration_ms': 0, 'memory_id': None})
    previous_gaps = prior['payload'].get('open_issues', []) if prior else []
    event('coordinator', 'resume_gaps' if prior else 'start_review', prior_issues=previous_gaps)
    previous = prior['payload'] if prior else {}
    previous_hashes = previous.get('source_fingerprints', {})
    hashes = {s['source_id']: fingerprint(s) for s in read.get('sources', [])}
    changed = sorted(sid for sid, value in hashes.items() if previous_hashes.get(sid) != value)
    event('coordinator', 'select_affected_checks', changed_sources=changed,
          selection='recheck_live_medical_account; preserve_unresolved_identity_funding_risk')
    # These are saved manual observations, never newly fetched by these roles.
    if previous.get('manual_observation_hash') != fingerprint([
            dossier['official_identity_observation'], dossier['external_form_observation']]):
        event('identity_risk', 'inspect_saved_official_observation', live_check=False,
              full_gate_passed=False)
        event('funding_channel', 'inspect_saved_allocation', amount_established=False, live_check=False)
    else:
        event('coordinator', 'retain_dated_manual_observations', live_check=False)
    analysis = analyze_read(read)  # Re-grounds every candidate against current retrieved text.
    event('rescue_need', 'ground_current_text_candidates', candidates=len(analysis['candidates']),
          fresh_network_read=not read.get('cached', False))
    fields = {c['field'] for c in analysis['candidates']}
    latest = analysis['latest_retrieved_statement']
    if {'reported_birth', 'reported_pregnancy'} <= fields:
        event('evaluator', 'request_chronology_resolution', issue='pregnant_vs_birth')
        if latest and latest['field'] == 'reported_birth' and analysis['all_configured_sources_read']:
            event('dispute_resolver', 'resolve_dated_progression', selected_source=latest['source_id'],
                  meaning='later_organization_account_not_independent_verification')
            event('coordinator', 'revise_case_account', selected_source=latest['source_id'])
        else:
            event('dispute_resolver', 'leave_chronology_unresolved', additional_fetches=0)
            latest = None
    event('evaluator', 'retain_six_unresolved_gates', qualified=False)
    complete = read.get('status') == 'read_complete'
    summary = {'qualified': False, 'remaining_minor': None, 'currency': 'CAD',
               'disposition': 'pending_evidence' if complete else 'source_check_incomplete',
               'gates': {g['gate']: False for g in dossier['gates']},
               'stop_reason': 'real_case_evidence_incomplete',
               'funding_notice': 'No validated case cost or raised total; remainder unknown.'}
    run_id = str(uuid4())
    result = {'case_id': CASE_ID, 'run_id': run_id, 'scenario_type': 'real_public_observations',
              'status': summary['disposition'], 'qualified': False, 'remaining_minor': None,
              'latest_retrieved_statement': latest if complete else None,
              'current_real_world_state_confirmed': False,
              'gaps': deepcopy(dossier['gates']), 'changed_sources': changed,
              'trace': trace, 'memory': {'status': memory_status, 'saved_memory_id': None,
                                        'recalled_memory_id': prior['memory_id'] if prior else None},
              'limits': ['Code roles, not live model planning.', 'Zero extra source or model calls.',
                         'Saved manual identity/allocation observations are not current rechecks.',
                         'Real case never uses synthetic qualification facts.']}
    if memory and memory_status != 'recall_failed':
        payload = {'schema_version': 1, 'case_id': CASE_ID, 'run_id': run_id,
                   'policy_profile': PROFILE, 'scenario_type': 'real_public_observations',
                   'review_date': datetime.now(timezone.utc).date().isoformat(),
                   'organization': dossier['organization_display_name'], 'case_name': dossier['case_name'],
                   'source_refs': [s['url'] for s in dossier['sources']],
                   'saved_manual_observations': {
                       'identity': deepcopy(dossier['official_identity_observation']),
                       'allocation': deepcopy(dossier['external_form_observation'])},
                   'source_fingerprints': hashes,
                   'manual_observation_hash': fingerprint([dossier['official_identity_observation'], dossier['external_form_observation']]),
                   'open_issues': deepcopy(dossier['gates']), 'review_summary': summary,
                   'claims': {str(i): c for i, c in enumerate(analysis['candidates'])},
                   'source_metadata': [{'source_id': s['source_id'], 'url': s['url'], 'published_metadata': s.get('published_metadata'),
                                        'status': s['status'], 'observed_at': read.get('observed_at')}
                                       for s in read.get('sources', [])],
                   'risk_hold': bool(previous.get('risk_hold', False))}
        began = time.monotonic()
        try:
            saved = memory.call('save', CASE_ID, payload)
            result['memory'].update(status='saved', saved_memory_id=saved['memory_id'])
            tools.append({'tool': 'hmem', 'operation': 'save', 'status': 'ok',
                          'duration_ms': int((time.monotonic()-began)*1000), 'memory_id': saved['memory_id']})
        except MemoryUnavailable:
            result['memory']['status'] = 'save_failed'
            tools.append({'tool': 'hmem', 'operation': 'save', 'status': 'failed',
                          'duration_ms': int((time.monotonic()-began)*1000), 'memory_id': None})
    if memory and result['memory']['status'] in ('recall_failed', 'save_failed'):
        result['status'] = 'review_incomplete'
    result['tools'] = tools
    result['duration_ms'] = elapsed_ms()
    return result
