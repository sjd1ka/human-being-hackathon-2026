import os
from copy import deepcopy
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from .memory import HMem, MemoryUnavailable
from .real_review import review_real_observations, CASE_ID


def observed(birth=True):
    sources = [{'source_id': 'appeal', 'status': 'read', 'url': 'https://guelphhumane.ca/appeal',
                'text': 'Lucy is only about a year old and pregnant and ready to give birth at any moment.',
                'published_metadata': '2026-10-13T15:00:00+00:00'}]
    if birth:
        sources.append({'source_id': 'update', 'status': 'read', 'url': 'https://guelphhumane.ca/update',
                        'text': 'Lucy gave birth and is mama of three beautiful kittens!',
                        'published_metadata': '2026-10-14T15:00:00+00:00'})
    return {'status': 'read_complete', 'sources': sources, 'observed_at': '2026-10-24T20:00:00+00:00'}


class RealReviewTests(TestCase):
    def test_evidence_triggers_feedback_and_no_qualification(self):
        first=review_real_observations(observed(False))
        later=review_real_observations(observed())
        self.assertNotIn('dispute_resolver',[e['role'] for e in first['trace']])
        self.assertIn('dispute_resolver',[e['role'] for e in later['trace']])
        self.assertIn('revise_case_account',[e['action'] for e in later['trace']])
        self.assertFalse(later['qualified'])
        self.assertIsNone(later['remaining_minor'])
        self.assertEqual(later['memory']['status'],'not_configured')

    def test_incomplete_read_does_not_keep_prior_account(self):
        read=observed()
        read['status']='read_incomplete'
        result=review_real_observations(read)
        self.assertIsNone(result['latest_retrieved_statement'])
        self.assertEqual(result['status'],'source_check_incomplete')

    def test_memory_failure_is_not_fake_success(self):
        class Failed:
            def call(self,*args): raise MemoryUnavailable()
        result=review_real_observations(observed(),Failed())
        self.assertEqual(result['status'],'review_incomplete')
        self.assertEqual(result['memory']['status'],'recall_failed')

    def test_steps_are_timed_in_order(self):
        trace=review_real_observations(observed())['trace']
        self.assertTrue(all(type(e['at_ms']) is int for e in trace))
        times=[e['at_ms'] for e in trace]
        self.assertEqual(times,sorted(times))

    def test_tools_without_memory_report_not_configured(self):
        result=review_real_observations(observed())
        self.assertEqual(result['tools'],[{'tool':'hmem','operation':'recall','status':'not_configured','duration_ms':0,'memory_id':None}])
        self.assertIsInstance(result['duration_ms'],int)

    def test_memory_failure_is_a_failed_tool_event(self):
        class Failed:
            def call(self,*args): raise MemoryUnavailable()
        result=review_real_observations(observed(),Failed())
        self.assertEqual(result['tools'][0]['status'],'failed')
        self.assertEqual(result['tools'][0]['operation'],'recall')
        self.assertEqual(result['status'],'review_incomplete')

    def test_save_failure_is_a_failed_tool_event(self):
        class SaveFails:
            def call(self,op,*args):
                if op=='recall': return {'entries':[]}
                raise MemoryUnavailable()
        result=review_real_observations(observed(),SaveFails())
        self.assertEqual([(t['operation'],t['status']) for t in result['tools']],[('recall','ok'),('save','failed')])
        self.assertEqual(result['status'],'review_incomplete')


@skipUnless(os.environ.get('PURRPOSE_HMEM_REFERENCE'),'Official H-MEM reference required')
class RealReviewMemoryTests(TestCase):
    def test_real_reference_recall_drives_recheck_and_preserves_history(self):
        with TemporaryDirectory() as root:
            ref=os.environ['PURRPOSE_HMEM_REFERENCE']
            first=review_real_observations(observed(False),HMem(ref,root,workspace='real-review-test'))
            second=review_real_observations(observed(),HMem(ref,root,workspace='real-review-test'))
            self.assertEqual(second['memory']['recalled_memory_id'],first['memory']['saved_memory_id'])
            self.assertEqual(second['trace'][0]['action'],'resume_gaps')
            self.assertTrue(second['trace'][0]['prior_issues'])
            mem=HMem(ref,root,workspace='real-review-test')
            entries=mem.call('recall',CASE_ID)['entries']
            self.assertEqual(len(entries),2)
            self.assertEqual(entries[0]['payload']['scenario_type'],'real_public_observations')
            self.assertFalse(entries[0]['payload']['review_summary']['qualified'])
            self.assertEqual(mem.call('recall','SYN-MAPLE')['entries'],[])
            third=review_real_observations(observed(),mem)
            self.assertIn('retain_dated_manual_observations',[e['action'] for e in third['trace']])
            self.assertEqual(third['changed_sources'],[])
