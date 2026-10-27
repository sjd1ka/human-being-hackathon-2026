"""Explicitly configured chat-model provider: Meterless Runtime or direct hosted NVIDIA.

No request runs on import. The route is chosen only by PURRPOSE_MODEL_PROVIDER;
there is no automatic fallback between providers. Missing caps fail closed.
A direct NVIDIA call is never reported as Nightshift/Meterless use.
"""
from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .extraction import Budget, ExtractionError, Limits

NVIDIA_URL = 'https://integrate.api.nvidia.com/v1/chat/completions'
LOOPBACK = {'127.0.0.1', 'localhost', '::1'}
APP_ID = 'purrpose'
CAPS = {'PURRPOSE_MODEL_MAX_CALLS': 'max_calls', 'PURRPOSE_MODEL_TOKEN_CAP': 'token_cap',
        'PURRPOSE_MODEL_CALLS_PER_MINUTE': 'per_minute', 'PURRPOSE_MODEL_INPUT_CHARS': 'input_chars',
        'PURRPOSE_MODEL_OUTPUT_TOKENS': 'output_tokens', 'PURRPOSE_MODEL_TIMEOUT_SECONDS': 'timeout_seconds'}
NAMES = ('PURRPOSE_MODEL_PROVIDER', 'NVIDIA_API_KEY', 'NVIDIA_MODEL', 'METERLESS_BASE_URL',
         'METERLESS_RUNTIME_TOKEN', 'METERLESS_MODEL', *CAPS)
CONNECTION = {'unauthorized': 'unauthorized', 'network_or_timeout': 'offline', 'rate_limited': 'rate_limited'}


class ProviderError(RuntimeError):
    def __init__(self, category):
        self.category = category
        super().__init__(category)  # Sanitized category only, never response text/key.


def category_for_status(code):
    return {401: 'unauthorized', 403: 'unauthorized', 404: 'model_not_found',
            429: 'rate_limited'}.get(code, 'provider_http_error')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError('redirect_rejected')


def http_transport(url, payload, headers, timeout):
    """One bounded POST, no redirects, no retries."""
    request = Request(url, data=json.dumps(payload).encode('utf-8'), method='POST',
                      headers={**headers, 'Content-Type': 'application/json'})
    try:
        with build_opener(NoRedirect).open(request, timeout=timeout) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ProviderError('provider_response_too_large')
            return json.loads(raw)
    except HTTPError as e:
        raise ProviderError(category_for_status(e.code)) from None
    except (TimeoutError, URLError, OSError):
        raise ProviderError('network_or_timeout') from None
    except (ValueError, UnicodeError):
        raise ProviderError('provider_invalid_json') from None


def http_get(url, headers, timeout):
    """One bounded GET for runtime discovery, no redirects, no retries."""
    try:
        with build_opener(NoRedirect).open(Request(url, headers=headers, method='GET'), timeout=timeout) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ProviderError('provider_response_too_large')
            return json.loads(raw)
    except HTTPError as e:
        raise ProviderError(category_for_status(e.code)) from None
    except (TimeoutError, URLError, OSError):
        raise ProviderError('network_or_timeout') from None
    except (ValueError, UnicodeError):
        raise ProviderError('provider_invalid_json') from None


def read_settings(env_file=None, environ=None):
    """Known names only, from an optional local env file, overridden by the environment."""
    values = {}
    if env_file and Path(env_file).is_file():
        for line in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                if k.strip() in NAMES:
                    values[k.strip()] = v.strip().strip('"\'')
    for k in NAMES:
        if environ and environ.get(k):
            values[k] = environ[k]
    return values


def meterless_url(base):
    parts = urlsplit(base if '://' in base else 'http://'+base)
    if parts.scheme not in ('http', 'https') or (parts.hostname or '').lower() not in LOOPBACK:
        return None
    path = parts.path.rstrip('/')
    for suffix in ('/v1/chat/completions', '/v1/models', '/healthz', '/v1'):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    return parts.scheme+'://'+parts.netloc+path+'/v1/chat/completions'


@dataclass(frozen=True)
class Route:
    name: str
    url: str
    model: str
    headers: dict
    extra: dict


def build_route(settings):
    name = settings.get('PURRPOSE_MODEL_PROVIDER')
    if name == 'nvidia_direct':
        key, model = settings.get('NVIDIA_API_KEY', ''), settings.get('NVIDIA_MODEL', '')
        if not key.strip() or not model.strip():
            raise ProviderError('provider_not_configured')
        # Explicit deployment option for the pinned Nemotron model: no hidden reasoning tokens.
        return Route(name, NVIDIA_URL, model, {'Authorization': 'Bearer '+key},
                     {'chat_template_kwargs': {'enable_thinking': False}})
    if name == 'meterless':
        token, model = settings.get('METERLESS_RUNTIME_TOKEN', ''), settings.get('METERLESS_MODEL', '')
        if not token.strip() or token.strip() == 'rt-local' or not model.strip():
            raise ProviderError('provider_not_configured')
        url = meterless_url(settings.get('METERLESS_BASE_URL', ''))
        if not url:
            raise ProviderError('base_url_not_allowed')
        # A pinned Nemotron lane otherwise reasons until Nightshift returns 502 empty_response;
        # routing modes may reach other models, so they get no model-specific options.
        extra = {'chat_template_kwargs': {'enable_thinking': False}} if model.startswith('nvidia/nemotron') else {}
        return Route(name, url, model, {'Authorization': 'Bearer '+token, 'meterless-app': APP_ID,
                                        'meterless-scope': 'user'}, extra)
    raise ProviderError('unknown_provider')


def build_caps(settings):
    try:
        caps = {field: int(settings[name]) for name, field in CAPS.items()}
    except (KeyError, ValueError):
        raise ProviderError('budget_not_configured') from None
    if any(v <= 0 for v in caps.values()):
        raise ProviderError('budget_not_configured')
    try:
        limits = Limits(caps['max_calls'], caps['token_cap'], caps['output_tokens']+caps['input_chars']//2,
                        caps['input_chars'], caps['output_tokens'], caps['timeout_seconds'])
        limits.validate()
    except ExtractionError as e:
        raise ProviderError(e.category) from None
    return limits, caps['per_minute']


class Provider:
    def __init__(self, settings, transport, clock, probe_transport=http_get):
        self.transport, self.clock, self.probe_transport = transport, clock, probe_transport
        self.route = self.budget = None
        self.per_minute = 0
        self.config_error = None
        self.requested = settings.get('PURRPOSE_MODEL_PROVIDER')
        try:
            self.route = build_route(settings)
            limits, self.per_minute = build_caps(settings)
            self.budget = Budget(limits)
        except ProviderError as e:
            self.config_error = e.category
        self.dispatched = deque()
        self.trace = []  # Last 50 sanitized call records; never message content or keys.
        self.connection, self.last_error, self.succeeded = 'untested', None, False

    @property
    def ready(self):
        return self.config_error is None

    def complete(self, messages):
        """One bounded chat completion. Returns the reply text or raises ProviderError."""
        if not self.ready:
            raise ProviderError(self.config_error)
        limits = self.budget.limits
        if sum(len(m.get('content') or '') for m in messages) > limits.input_chars:
            raise ProviderError('input_limit_reached')
        now = self.clock()
        while self.dispatched and now - self.dispatched[0] >= 60:
            self.dispatched.popleft()
        if len(self.dispatched) >= self.per_minute:
            raise ProviderError('rate_cap_reached')
        try:
            self.budget.reserve()
        except ExtractionError as e:
            raise ProviderError(e.category) from None
        self.dispatched.append(now)
        payload = {'model': self.route.model, 'messages': messages, 'temperature': 0,
                   'max_tokens': limits.output_tokens, 'stream': False, **self.route.extra}
        started = time.monotonic()
        entry = {'route': self.route.name, 'model': self.route.model, 'returned_model': None,
                 'usage': None, 'finish_reason': None}
        try:
            response = self.transport(self.route.url, payload, self.route.headers, limits.timeout_seconds)
        except Exception as e:
            self.budget.settle(None)  # Possibly billed: keep the reservation, usage unknown.
            category = e.category if isinstance(e, ProviderError) else 'provider_transport_failed'
            self._record(entry, started, category)
            raise ProviderError(category) from None
        usage = response.get('usage') if isinstance(response, dict) else None
        self.budget.settle(usage)
        entry.update(usage=usage if isinstance(usage, dict) else None,
                     returned_model=response.get('model') if isinstance(response, dict) else None)
        try:
            choice = response['choices'][0]
            entry['finish_reason'] = choice.get('finish_reason')
            text = choice['message']['content']
        except (KeyError, TypeError, IndexError, AttributeError):
            self._record(entry, started, 'provider_invalid_response')
            raise ProviderError('provider_invalid_response') from None
        if entry['finish_reason'] != 'stop' or not isinstance(text, str) or not text.strip():
            self._record(entry, started, 'incomplete_output')
            raise ProviderError('incomplete_output')
        self._record(entry, started, None)
        return text

    def _record(self, entry, started, error):
        entry.update(status='failed' if error else 'success', error_category=error,
                     latency_ms=round((time.monotonic()-started)*1000))
        self.trace = self.trace[-49:]+[entry]
        self.last_error = error
        if error is None:
            self.connection, self.succeeded = 'online', True
        elif error in CONNECTION:
            self.connection = CONNECTION[error]

    def probe(self):
        """Meterless discovery: GET /v1/models decides online/unauthorized/offline. Not inference."""
        if not self.ready or self.route.name != 'meterless':
            return {'probed': False, 'connection': self.connection}
        url = self.route.url[:-len('/chat/completions')]+'/models'
        headers = {k: v for k, v in self.route.headers.items() if k != 'meterless-scope'}  # scope is for chat
        try:
            listing = self.probe_transport(url, headers, self.budget.limits.timeout_seconds)
        except ProviderError as e:
            self.connection = CONNECTION.get(e.category, 'error')
            return {'probed': True, 'connection': self.connection, 'error_category': e.category}
        except Exception:
            self.connection = 'error'
            return {'probed': True, 'connection': 'error', 'error_category': 'provider_transport_failed'}
        data = listing.get('data') if isinstance(listing, dict) else None
        modes = sorted(m['id'] for m in data or [] if isinstance(m, dict) and isinstance(m.get('id'), str)
                       and m['id'].startswith('meterless/'))
        if not modes:
            return {'probed': True, 'connection': 'no_meterless_modes', 'modes': []}
        self.connection = 'online'
        return {'probed': True, 'connection': 'online', 'modes': modes, 'model_listed': self.route.model in modes}

    def status(self):
        if not self.ready or self.route.name != 'meterless':
            nightshift = 'not_connected'
        else:
            nightshift = 'meterless_runtime_request_succeeded' if self.succeeded else 'configured_untested'
        return {'requested_provider': self.requested, 'route': self.route.name if self.route else None,
                'model': self.route.model if self.route else None, 'ready': self.ready,
                'config_error': self.config_error, 'connection': self.connection,
                'last_error': self.last_error, 'nightshift': nightshift,
                'budget': {**self.budget.status(), 'max_calls': self.budget.limits.max_calls,
                           'token_cap': self.budget.limits.token_cap,
                           'calls_per_minute': self.per_minute} if self.budget else None,
                'retries': 0, 'automatic_provider_fallback': False}


def from_settings(settings, transport=http_transport, clock=time.monotonic, probe_transport=http_get):
    """None when no provider is requested (model off); otherwise a Provider, ready or failing closed."""
    if not settings.get('PURRPOSE_MODEL_PROVIDER'):
        return None
    return Provider(settings, transport, clock, probe_transport)
