import json
from unittest import TestCase
from .chat_intent import ONTARIO_CITIES, validate_intent


class ModelIntentBoundaryTests(TestCase):
    def test_narrow_discovery_proposal(self):
        obj = {'intent': 'discover', 'city': None, 'region_wide': True}
        self.assertEqual(validate_intent(json.dumps(obj)), obj)

    def test_tool_or_decision_fields_rejected(self):
        for obj in ({'intent': 'pay', 'city': None, 'region_wide': False},
                    {'intent': 'discover', 'city': 'Ottawa', 'region_wide': True},
                    {'intent': 'discover', 'city': None, 'region_wide': True, 'qualified': True}):
            with self.assertRaises(ValueError):
                validate_intent(json.dumps(obj))

    def test_bad_or_unbounded_response_rejected(self):
        for candidate in ('[]', 'null', 'not json', 'x'*2049):
            with self.assertRaises(ValueError):
                validate_intent(candidate)

    def test_full_chat_intent_set_accepted(self):
        for intent in ('greet', 'amount', 'allocation', 'evidence', 'gaps', 'select_real_case', 'history',
                       'organization_checklist', 'confirm_expansion', 'clarify'):
            obj = {'intent': intent, 'city': None, 'region_wide': False}
            self.assertEqual(validate_intent(json.dumps(obj)), obj)

    def test_fictional_demo_may_name_a_city(self):
        obj = {'intent': 'fictional_demo', 'city': 'Ottawa', 'region_wide': False}
        self.assertEqual(validate_intent(json.dumps(obj)), obj)

    def test_model_cannot_request_refresh_or_actions(self):
        for intent in ('refresh', 'refresh_request', 'pay', 'update_source', 'qualify'):
            with self.assertRaises(ValueError):
                validate_intent(json.dumps({'intent': intent, 'city': None, 'region_wide': False}))

    def test_json_inside_code_fence_accepted(self):
        obj = {'intent': 'greet', 'city': None, 'region_wide': False}
        self.assertEqual(validate_intent('```json\n'+json.dumps(obj)+'\n```'), obj)

    def test_null_region_wide_means_false(self):
        # Observed live: Nemotron writes null for "not region-wide" on non-discovery intents.
        self.assertEqual(validate_intent('{"intent": "greet", "city": null, "region_wide": null}'),
                         {'intent': 'greet', 'city': None, 'region_wide': False})
        for bad in ('"yes"', '1', '[]'):
            with self.assertRaises(ValueError):
                validate_intent('{"intent": "greet", "city": null, "region_wide": '+bad+'}')

    def test_outside_area_carries_no_location(self):
        obj = {'intent': 'outside_area', 'city': None, 'region_wide': False}
        self.assertEqual(validate_intent(json.dumps(obj)), obj)
        self.assertEqual(validate_intent(json.dumps({'intent': 'outside_area', 'city': None, 'region_wide': True})), obj)

    def test_stray_location_on_other_intents_is_dropped_not_fatal(self):
        # Observed live 26 Oct: {"intent": "organization_checklist", "city": null, "region_wide": true}
        # used to reject the whole proposal.
        for name in ('amount', 'organization_checklist', 'list_organizations', 'clarify'):
            for city, region in (('Ottawa', False), (None, True)):
                with self.subTest(name=name, city=city):
                    self.assertEqual(validate_intent(json.dumps({'intent': name, 'city': city, 'region_wide': region})),
                                     {'intent': name, 'city': None, 'region_wide': False})

    def test_any_listed_ontario_city_is_accepted_and_normalized(self):
        for given, expected in (('Guelph', 'Guelph'), ('guelph', 'Guelph'), ('HAMILTON', 'Hamilton'), ('Thunder Bay', 'Thunder Bay')):
            with self.subTest(given=given):
                self.assertEqual(validate_intent(json.dumps({'intent': 'discover', 'city': given, 'region_wide': False}))['city'], expected)
        self.assertIn('Guelph', ONTARIO_CITIES)

    def test_unknown_city_is_dropped_rather_than_trusted(self):
        for given in ('Vancouver', 'Atlantis', '<script>', 'x'*80):
            with self.subTest(given=given):
                self.assertEqual(validate_intent(json.dumps({'intent': 'discover', 'city': given, 'region_wide': False})),
                                 {'intent': 'discover', 'city': None, 'region_wide': False})

    def test_new_request_types_accepted(self):
        for name in ('list_organizations', 'about', 'donate_how', 'thanks'):
            obj = {'intent': name, 'city': None, 'region_wide': False}
            self.assertEqual(validate_intent(json.dumps(obj)), obj)
