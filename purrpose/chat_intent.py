"""Model-integration boundary: validates a configured model's intent proposal.

A model proposes only a narrow intent; ordinary conversation text cannot become
SQL, tool calls, source refreshes, evidence or a qualification decision.
"""
import json
import re

INTENTS = ('greet', 'discover', 'amount', 'allocation', 'evidence', 'gaps', 'select_real_case', 'history',
           'organization_checklist', 'list_organizations', 'about', 'donate_how', 'thanks',
           'fictional_demo', 'confirm_expansion', 'outside_area', 'clarify')
CITY_INTENTS = ('discover', 'fictional_demo')
# Ontario municipalities a user may name. A listed name is only a search preference: a case's
# treatment city still has to match its sources, so naming a city never invents a case there.
ONTARIO_CITIES = ('Ottawa', 'Toronto', 'Guelph', 'Hamilton', 'London', 'Kitchener', 'Waterloo', 'Cambridge',
                  'Mississauga', 'Brampton', 'Markham', 'Vaughan', 'Richmond Hill', 'Oakville', 'Burlington',
                  'Oshawa', 'Whitby', 'Ajax', 'Pickering', 'Barrie', 'Kingston', 'Windsor', 'Sudbury',
                  'Thunder Bay', 'Peterborough', 'St. Catharines', 'Niagara Falls', 'Belleville', 'Sarnia',
                  'Sault Ste. Marie', 'North Bay', 'Brantford', 'Etobicoke', 'Scarborough', 'North York')
_CITY_BY_KEY = {c.casefold(): c for c in ONTARIO_CITIES}


def ontario_city(name):
    """The listed spelling of an Ontario city, or None for anything else."""
    return _CITY_BY_KEY.get(name.strip().casefold()) if isinstance(name, str) and len(name) <= 40 else None


def validate_intent(candidate):
    """Validate a model's JSON proposal before the coordinator uses it."""
    if not isinstance(candidate, str) or len(candidate) > 2048:
        raise ValueError('Invalid intent response')
    fenced = re.fullmatch(r'\s*```(?:json)?\s*(.*?)\s*```\s*', candidate, re.S)
    try:
        value = json.loads(fenced[1] if fenced else candidate)
    except ValueError:
        raise ValueError('Invalid intent response') from None
    if not isinstance(value, dict) or set(value) != {'intent', 'city', 'region_wide'}:
        raise ValueError('Invalid intent schema')
    if value['intent'] not in INTENTS:
        raise ValueError('Unsupported intent')
    if value['region_wide'] is None:
        value['region_wide'] = False  # Null can only mean "not region-wide"; other non-booleans still fail.
    if type(value['region_wide']) is not bool or (value['city'] is not None and not isinstance(value['city'], str)):
        raise ValueError('Unsupported preference')
    if value['intent'] not in CITY_INTENTS:
        # A location flag on a non-search intent cannot change anything; drop it instead of losing the intent.
        return {'intent': value['intent'], 'city': None, 'region_wide': False}
    if value['city'] and value['region_wide']:
        raise ValueError('Ambiguous preference')
    # An unlisted city (another province, a made-up place, injected text) is dropped, never trusted.
    return {**value, 'city': ontario_city(value['city'])}
