import unittest
from types import SimpleNamespace
from .directory import select_candidates,SQL
from .directory_chat import handle

class DirectoryTests(unittest.TestCase):
    def test_sort_and_filter_not_trust(self):
        rows=[['123456789RR0001','Z Cats','Z Cats','Toronto','ON','0180','3'],
              ['123456780RR0001','A Feline','A Feline','Ottawa','ON','0180','3'],
              ['123456781RR0001','Education','Education','Ottawa','ON','0180','3']]
        result,summary=select_candidates(rows)
        self.assertEqual([r['reported_city'] for r in result],['Ottawa','Toronto'])
        self.assertFalse(any(r['qualified'] for r in result))
        self.assertEqual(summary['matching_cat_name_records'],2)
        self.assertNotIn('WHERE',SQL)

    def test_everyday_help_request_enters_live_discovery(self):
        state={}
        result=handle(SimpleNamespace(),state,'I want to help a cat',False)
        self.assertTrue(state['pending_directory'])
        self.assertIn('Ontario city',result['reply'])

    def test_unconfigured_zetaris_is_disclosed_and_records_no_agent_work(self):
        from .server import LocalApp
        app=LocalApp()  # default registry: no remote Zetaris JDBC
        answer=app.conversation.reply('nz','find cat rescue organizations in Toronto')
        self.assertIn('Zetaris',answer['reply'])
        self.assertIn('not configured',answer['reply'])
        self.assertNotIn('could not return matching candidates',answer['reply'])
        run=app.runs.runs[-1]
        ran={a['agent'] for a in run['agents'] if a['ran']}
        self.assertEqual(ran,{'orchestrator'})
        self.assertEqual(next(a for a in run['agents'] if a['agent']=='orchestrator')['decision'],'stop directory not configured')
        self.assertNotIn('directory_result',answer)
        collector=next(a for a in run['agents'] if a['agent']=='collector')
        self.assertIn('Zetaris',collector['skipped_reason'])
        self.assertEqual([(t['tool'],t['status']) for t in run['tools']],[('zetaris','not_configured')])

    def test_every_listed_city_gives_a_valid_memory_scope(self):
        import re
        from .chat_intent import ONTARIO_CITIES
        from .directory import directory_case_id
        for city in (*ONTARIO_CITIES,None):
            self.assertRegex(directory_case_id(city),r'^[a-zA-Z0-9_-]{1,64}$')  # HMem.call rejects anything else
        self.assertEqual(directory_case_id('St. Catharines'),'DIRECTORY-ON-ST-CATHARINES')
        self.assertEqual(directory_case_id('Sault Ste. Marie'),'DIRECTORY-ON-SAULT-STE-MARIE')
        self.assertEqual(directory_case_id(None),'DIRECTORY-ON-ALL')

    def test_conflicting_identifier_excluded(self):
        row=['123456789RR0001','Cats','Cats','Toronto','ON','0180','2']
        other=list(row);other[1]='Other Cats'
        result,summary=select_candidates([row,other])
        self.assertEqual(result,[])
        self.assertEqual(summary['conflicting_identifiers'],1)

    def test_chat_asks_location_then_reuses_observations(self):
        calls=[]
        def dispatch(path,data):
            calls.append((path,data))
            return {'status':'candidate_checks_completed','candidates':[{'organization_full_name':'Cats'}]}
        app=SimpleNamespace(dispatch=dispatch);state={}
        self.assertIn('Which Ontario city',handle(app,state,'help me find reliable cat rescue organizations',False)['reply'])
        self.assertEqual(calls,[])
        self.assertIn('directory_result',handle(app,state,'Ontario',False))
        handle(app,state,'what evidence is missing?',False)
        self.assertEqual(len(calls),1)
        self.assertIsNone(handle(app,{},'do not find cat rescue organizations in Ontario',False))

class EverydayLanguageTests(unittest.TestCase):
    def app(self):
        self.calls=[]
        def dispatch(path,data):
            self.calls.append((path,data))
            return {'status':'candidate_checks_completed','candidates':[{'organization_full_name':'Example Cats'}]}
        return SimpleNamespace(dispatch=dispatch)

    def test_paraphrases(self):
        phrases=["I'd like to help some cats in Toronto",'Can you suggest cat shelters in Toronto?',
                 'Looking for a cat rescue in Toronto','Where can I donate to help kittens in Toronto?',
                 'Show me cat charities in Toronto','I wanna support kitties in Toronto',
                 'pls find cat resuce orgnizations in Toronto','我想给多伦多的猫捐款',
                 '帮我找安省的猫救助机构','有没有安省可以帮助小猫的组织']
        app=self.app()
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                result=handle(app,{},phrase,False)
                self.assertIn('directory_result',result)
        self.assertEqual(len(self.calls),len(phrases))

    def test_ambiguity_never_fetches_or_falls_back(self):
        app=self.app();state={}
        for phrase in ('I want to help cats near me','Toronto or Ottawa?','what about that?'):
            self.assertIsNotNone(handle(app,state,phrase,False))
        self.assertEqual(self.calls,[])
        result=handle(app,state,'anywhere',False)
        self.assertIn('directory_result',result)
        self.assertEqual(self.calls[0][1],{'city':None})
        handle(app,state,'is this legit?',False)
        handle(app,state,'what now?',False)
        self.assertEqual(len(self.calls),1)

    def test_org_role_clarifies_instead_of_search(self):
        app=self.app();state={}
        result=handle(app,state,'We run a cat shelter and need help with our website',False)
        self.assertTrue(state['awaiting_organization_url'])
        self.assertNotIn('directory_result',result)
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
