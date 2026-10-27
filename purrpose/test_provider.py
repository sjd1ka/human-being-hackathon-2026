import json
from unittest import TestCase

from .provider import ProviderError, category_for_status, from_settings

KEY = 'nvapi-test-secret-do-not-leak'
CAPS = {'PURRPOSE_MODEL_MAX_CALLS': '5', 'PURRPOSE_MODEL_TOKEN_CAP': '20000',
        'PURRPOSE_MODEL_CALLS_PER_MINUTE': '3', 'PURRPOSE_MODEL_INPUT_CHARS': '4000',
        'PURRPOSE_MODEL_OUTPUT_TOKENS': '300', 'PURRPOSE_MODEL_TIMEOUT_SECONDS': '30'}
NVIDIA = {'PURRPOSE_MODEL_PROVIDER': 'nvidia_direct', 'NVIDIA_API_KEY': KEY,
          'NVIDIA_MODEL': 'nvidia/nemotron-3.5-lightning-30b-a3b', **CAPS}
METERLESS = {'PURRPOSE_MODEL_PROVIDER': 'meterless', 'METERLESS_BASE_URL': 'http://127.0.0.1:8088',
             'METERLESS_RUNTIME_TOKEN': 'rt-real-token', 'METERLESS_MODEL': 'meterless/auto',
             **CAPS, 'PURRPOSE_MODEL_TIMEOUT_SECONDS': '180'}
OK = {'model': 'nvidia/nemotron-3.5-lightning-30b-a3b',
      'choices': [{'finish_reason': 'stop', 'message': {'content': '{"intent": "greet"}'}}],
      'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}}
MESSAGES = [{'role': 'system', 'content': 'classify'}, {'role': 'user', 'content': 'hello'}]


class FakeTransport:
    def __init__(self, result=OK):
        self.result, self.calls = result, []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append({'url': url, 'payload': payload, 'headers': headers, 'timeout': timeout})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(settings, result=OK, clock=None):
    transport = FakeTransport(result)
    return from_settings(settings, transport=transport, clock=clock or Clock()), transport


class ConfigurationTests(TestCase):
    def test_no_provider_setting_means_model_off(self):
        self.assertIsNone(from_settings({'NVIDIA_API_KEY': KEY, **CAPS}))

    def test_missing_cap_fails_closed_without_calling(self):
        settings = dict(NVIDIA)
        del settings['PURRPOSE_MODEL_CALLS_PER_MINUTE']
        provider, transport = make(settings)
        self.assertFalse(provider.ready)
        with self.assertRaises(ProviderError) as e:
            provider.complete(MESSAGES)
        self.assertEqual(e.exception.category, 'budget_not_configured')
        self.assertEqual(transport.calls, [])

    def test_missing_credentials_or_model_fail_closed(self):
        for name in ('NVIDIA_API_KEY', 'NVIDIA_MODEL'):
            settings = dict(NVIDIA)
            del settings[name]
            provider, _ = make(settings)
            self.assertEqual(provider.config_error, 'provider_not_configured')

    def test_unknown_provider_rejected(self):
        provider, _ = make({**NVIDIA, 'PURRPOSE_MODEL_PROVIDER': 'openai'})
        self.assertEqual(provider.config_error, 'unknown_provider')

    def test_meterless_must_be_loopback_with_real_token(self):
        provider, _ = make({**METERLESS, 'METERLESS_BASE_URL': 'https://example.com/v1'})
        self.assertEqual(provider.config_error, 'base_url_not_allowed')
        provider, _ = make({**METERLESS, 'METERLESS_RUNTIME_TOKEN': 'rt-local'})
        self.assertEqual(provider.config_error, 'provider_not_configured')


class RequestShapeTests(TestCase):
    def test_nvidia_direct_uses_fixed_endpoint_and_disables_thinking(self):
        provider, transport = make(NVIDIA)
        self.assertEqual(provider.complete(MESSAGES), '{"intent": "greet"}')
        call = transport.calls[0]
        self.assertEqual(call['url'], 'https://integrate.api.nvidia.com/v1/chat/completions')
        self.assertEqual(call['headers']['Authorization'], 'Bearer '+KEY)
        self.assertEqual(call['payload']['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(call['payload']['max_tokens'], 300)
        self.assertEqual(call['payload']['temperature'], 0)
        self.assertFalse(call['payload']['stream'])
        self.assertEqual(call['timeout'], 30)

    def test_meterless_contract_headers_and_single_v1(self):
        for base in ('http://127.0.0.1:8088', 'http://127.0.0.1:8088/v1/', 'http://localhost:8088/v1/chat/completions'):
            provider, transport = make({**METERLESS, 'METERLESS_BASE_URL': base})
            provider.complete(MESSAGES)
            call = transport.calls[0]
            self.assertTrue(call['url'].endswith(':8088/v1/chat/completions'), call['url'])
            self.assertNotIn('/v1/v1', call['url'])
            self.assertEqual(call['headers']['meterless-app'], 'purrpose')
            self.assertEqual(call['headers']['meterless-scope'], 'user')
            self.assertEqual(call['payload']['model'], 'meterless/auto')
            self.assertNotIn('chat_template_kwargs', call['payload'])
            self.assertEqual(call['timeout'], 180)

    def test_meterless_pinned_nemotron_disables_thinking(self):
        # Nightshift 1.2.7 returns 502 empty_response when Nemotron spends the whole budget reasoning.
        provider, transport = make({**METERLESS, 'METERLESS_MODEL': 'nvidia/nemotron-3.5-lightning-30b-a3b'})
        provider.complete(MESSAGES)
        self.assertEqual(transport.calls[0]['payload']['chat_template_kwargs'], {'enable_thinking': False})
        provider, transport = make({**METERLESS, 'METERLESS_MODEL': 'nvidia/meta/muse-glimmer-30b'})
        provider.complete(MESSAGES)
        self.assertNotIn('chat_template_kwargs', transport.calls[0]['payload'])


class LimitTests(TestCase):
    def test_per_minute_cap_blocks_before_dispatch(self):
        clock = Clock()
        provider, transport = make(NVIDIA, clock=clock)
        for _ in range(3):
            provider.complete(MESSAGES)
        with self.assertRaises(ProviderError) as e:
            provider.complete(MESSAGES)
        self.assertEqual(e.exception.category, 'rate_cap_reached')
        self.assertEqual(len(transport.calls), 3)
        clock.now += 61
        provider.complete(MESSAGES)
        self.assertEqual(len(transport.calls), 4)

    def test_total_call_cap_blocks(self):
        clock = Clock()
        provider, transport = make({**NVIDIA, 'PURRPOSE_MODEL_MAX_CALLS': '2'}, clock=clock)
        provider.complete(MESSAGES)
        provider.complete(MESSAGES)
        with self.assertRaises(ProviderError) as e:
            provider.complete(MESSAGES)
        self.assertEqual(e.exception.category, 'call_cap_reached')
        self.assertEqual(len(transport.calls), 2)

    def test_oversized_input_blocked_before_dispatch(self):
        provider, transport = make(NVIDIA)
        with self.assertRaises(ProviderError) as e:
            provider.complete([{'role': 'user', 'content': 'x'*4001}])
        self.assertEqual(e.exception.category, 'input_limit_reached')
        self.assertEqual(transport.calls, [])


class FailureTests(TestCase):
    def test_rate_limited_is_not_retried(self):
        provider, transport = make(NVIDIA, result=ProviderError('rate_limited'))
        with self.assertRaises(ProviderError) as e:
            provider.complete(MESSAGES)
        self.assertEqual(e.exception.category, 'rate_limited')
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(provider.status()['last_error'], 'rate_limited')

    def test_timeout_keeps_usage_uncertain(self):
        provider, _ = make(NVIDIA, result=ProviderError('network_or_timeout'))
        with self.assertRaises(ProviderError):
            provider.complete(MESSAGES)
        status = provider.status()
        self.assertEqual(status['budget']['uncertain_calls'], 1)
        self.assertEqual(status['budget']['spent_tokens'], 0)
        self.assertIsNone(provider.trace[-1]['usage'])

    def test_truncated_or_empty_output_rejected(self):
        for choice in ({'finish_reason': 'length', 'message': {'content': '{"intent"'}},
                       {'finish_reason': 'stop', 'message': {'content': None}}):
            provider, _ = make(NVIDIA, result={**OK, 'choices': [choice]})
            with self.assertRaises(ProviderError) as e:
                provider.complete(MESSAGES)
            self.assertEqual(e.exception.category, 'incomplete_output')

    def test_http_status_categories(self):
        self.assertEqual(category_for_status(401), 'unauthorized')
        self.assertEqual(category_for_status(403), 'unauthorized')
        self.assertEqual(category_for_status(404), 'model_not_found')
        self.assertEqual(category_for_status(429), 'rate_limited')
        self.assertEqual(category_for_status(500), 'provider_http_error')


class StatusTests(TestCase):
    def test_direct_nvidia_never_claims_nightshift(self):
        provider, _ = make(NVIDIA)
        provider.complete(MESSAGES)
        status = provider.status()
        self.assertEqual(status['route'], 'nvidia_direct')
        self.assertEqual(status['nightshift'], 'not_connected')
        self.assertEqual(status['budget']['spent_tokens'], 120)
        self.assertEqual(status['connection'], 'online')

    def test_meterless_success_is_recorded_as_runtime_use(self):
        provider, _ = make(METERLESS)
        self.assertEqual(provider.status()['nightshift'], 'configured_untested')
        provider.complete(MESSAGES)
        self.assertEqual(provider.status()['nightshift'], 'meterless_runtime_request_succeeded')

    def test_unauthorized_is_not_reported_offline(self):
        provider, _ = make(METERLESS, result=ProviderError('unauthorized'))
        with self.assertRaises(ProviderError):
            provider.complete(MESSAGES)
        self.assertEqual(provider.status()['connection'], 'unauthorized')

    def test_secrets_never_in_status_or_trace(self):
        provider, _ = make(NVIDIA)
        provider.complete(MESSAGES)
        dumped = json.dumps([provider.status(), provider.trace])
        self.assertNotIn(KEY, dumped)
        self.assertNotIn('hello', dumped)  # no message content in trace


class FakeGet:
    def __init__(self, result):
        self.result, self.calls = result, []

    def __call__(self, url, headers, timeout):
        self.calls.append({'url': url, 'headers': headers, 'timeout': timeout})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def probe_with(settings, result):
    get = FakeGet(result)
    return from_settings(settings, transport=FakeTransport(), clock=Clock(), probe_transport=get), get


class MeterlessDiscoveryTests(TestCase):
    MODELS = {'data': [{'id': 'meterless/auto'}, {'id': 'meterless/fast'}, {'id': 'meterless/new-mode'}]}

    def test_models_listing_decides_online(self):
        provider, get = probe_with(METERLESS, self.MODELS)
        result = provider.probe()
        self.assertEqual(get.calls[0]['url'], 'http://127.0.0.1:8088/v1/models')
        self.assertEqual(get.calls[0]['headers']['meterless-app'], 'purrpose')
        self.assertEqual(result['connection'], 'online')
        self.assertIn('meterless/new-mode', result['modes'])  # unknown meterless ids are kept
        self.assertTrue(result['model_listed'])
        self.assertEqual(provider.status()['connection'], 'online')
        self.assertEqual(provider.status()['budget']['calls'], 0)  # discovery is not inference

    def test_wrong_token_is_unauthorized_and_runtime_down_is_offline(self):
        provider, _ = probe_with(METERLESS, ProviderError('unauthorized'))
        self.assertEqual(provider.probe()['connection'], 'unauthorized')
        provider, _ = probe_with(METERLESS, ProviderError('network_or_timeout'))
        self.assertEqual(provider.probe()['connection'], 'offline')

    def test_listing_without_meterless_modes_is_not_online(self):
        provider, _ = probe_with(METERLESS, {'data': [{'id': 'nvidia/something'}]})
        result = provider.probe()
        self.assertEqual(result['connection'], 'no_meterless_modes')
        self.assertNotEqual(provider.status()['connection'], 'online')

    def test_success_of_listing_alone_is_not_nightshift_use(self):
        provider, _ = probe_with(METERLESS, self.MODELS)
        provider.probe()
        self.assertEqual(provider.status()['nightshift'], 'configured_untested')

    def test_nvidia_direct_is_not_probed(self):
        provider, get = probe_with(NVIDIA, self.MODELS)
        self.assertFalse(provider.probe()['probed'])
        self.assertEqual(get.calls, [])
