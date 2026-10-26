from unittest import TestCase
from unittest.mock import patch
from .server import LocalApp


class RealResearchChatTests(TestCase):
    def setUp(self):
        self.app=LocalApp()

    def say(self,text,session='one'):
        return self.app.dispatch('/api/chat',{'session_id':session,'message':text})

    def test_real_context_amount_and_allocation(self):
        self.assertIn('research',self.say('Tell me about Lucy'))
        answer=self.say('还缺多少钱？')
        self.assertIn('未知',answer['reply'])
        self.assertIsNone(answer['research']['remaining_minor'])
        self.assertIn('other GHS animals',self.say('Where does the money go?')['reply'])
        self.assertIsNone(self.app.latest_run)

    def test_explicit_fixture_selection_clears_research_context(self):
        self.say('Lucy')
        self.assertIn('results',self.say('fictional Ottawa'))
        self.assertNotIn('research',self.say('How much?'))

    def test_sessions_do_not_share_research_context(self):
        self.say('Lucy')
        self.assertNotIn('research',self.say('How much?',session='two'))

    def test_no_qualification_or_new_fetch_from_latest_query(self):
        answer=self.say('latest evidence for Lucy')
        self.assertFalse(answer['research']['qualified'])
        self.assertIn('did not fetch',answer['reply'])
        self.assertEqual(answer['new_cloud_calls'],0)

    def test_gap_list_retains_privacy_boundary(self):
        answer=self.say('Lucy 还缺什么资料')
        self.assertIn('不要',answer['reply'])
        self.assertTrue(answer['research']['gates'])

    def test_explicit_refresh_only_and_bounded_cache(self):
        with patch('purrpose.server.bounded_read', return_value={'status':'read_complete','sources':[]}) as read:
            self.say('Tell me about Lucy')
            self.say('How much?')
            self.assertEqual(read.call_count,0)
            answer=self.say('refresh Lucy')
            self.assertIn('live_read',answer)
            self.assertFalse(answer['research']['qualified'])
            duplicate=self.say('重新检查官网')
            self.assertTrue(duplicate['live_read']['cached'])
            self.assertEqual(read.call_count,1)

    def test_failed_refresh_remains_visible_in_followups(self):
        with patch('purrpose.server.bounded_read',return_value={'status':'read_incomplete','sources':[], 'stage':'robots','error':'network_or_timeout'}):
            answer=self.say('refresh Lucy')
            self.assertEqual(answer['live_read']['stage'],'robots')
            self.assertIn('not fully complete',answer['reply'])
            later=self.say('How much?')
            self.assertIn('not confirmed current',later['reply'])
            self.assertIsNone(later['research']['remaining_minor'])

    def test_real_history_without_memory_is_explicitly_unavailable(self):
        answer=self.say('Lucy history')
        self.assertEqual(answer['research_history']['status'],'history_unavailable')
        self.assertNotIn('results',answer)

    def test_generic_discovery_defaults_to_real_then_follows_case(self):
        self.say('I want to help a cat')
        result=self.say('anywhere in Ontario')
        self.assertEqual(result['results']['collection'],'real')
        self.assertEqual(result['results']['qualified'],[])
        self.assertIn('research',self.say('How much?'))
        self.assertIsNone(self.app.latest_run)

    def test_city_does_not_silently_switch_to_synthetic(self):
        result=self.say('Ottawa')
        self.assertEqual(result['results']['collection'],'real')
        self.assertEqual(result['results']['status'],'no_city_match')
        self.assertIsNone(self.app.latest_run)

    def test_refresh_reports_run_and_cached_read_does_not(self):
        with patch('purrpose.server.bounded_read',return_value={'status':'read_complete','sources':[]}):
            first=self.say('refresh Lucy')
            self.assertIsNotNone(first['agent_run']['run_id'])
            self.assertEqual(first['agent_run']['note'],'New review run')
            self.assertEqual(first['live_read']['run_id'],first['agent_run']['run_id'])
            second=self.say('refresh Lucy')
            self.assertIsNone(second['agent_run']['run_id'])
            self.assertEqual(second['agent_run']['note'],'Reused a recent source read; no new run')
            self.assertEqual(len(self.app.runs.summaries()),1)
            summary=self.app.runs.summaries()[0]
            self.assertEqual(summary['kind'],'real')
            self.assertEqual(summary['session_label'],'one')

    def test_plain_follow_up_has_no_run(self):
        self.say('Lucy')
        answer=self.say('Lucy what evidence is missing?')
        self.assertEqual(answer['agent_run'],{'run_id':None,'note':'Answered from saved results; no agents ran','model':None})
        self.assertEqual(self.app.runs.summaries(),[])

    def test_fictional_chat_answer_reports_fictional_run(self):
        self.say('fictional Ottawa')
        answer=self.say('How much?')
        self.assertEqual(answer['agent_run']['note'],'New review run')
        run=self.app.runs.get(answer['agent_run']['run_id'])
        self.assertEqual(run['kind'],'fictional')

    def test_failed_read_still_records_run_with_tool_row(self):
        with patch('purrpose.server.bounded_read',return_value={'status':'read_incomplete','sources':[],'stage':'robots','error':'network_or_timeout'}):
            answer=self.say('refresh Lucy')
        run=self.app.runs.get(answer['agent_run']['run_id'])
        self.assertEqual(run['tools'][0]['status'],'not_configured')
        self.assertEqual(run['status'],'source_check_incomplete')
