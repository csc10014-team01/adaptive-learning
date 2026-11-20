"""Ollama transport for the frozen grading proposal (independent of generation)."""
import json
import time
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

PROVIDER_KEYS = ('model', 'done', 'done_reason', 'prompt_eval_count', 'eval_count',
                 'load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration')

def strict(text):
 def pairs(items):
  d={}
  for k,v in items:
   if k in d:raise ValueError('Duplicate JSON key')
   d[k]=v
  return d
 def fail(x):raise ValueError('Nonfinite JSON')
 return json.loads(text,object_pairs_hook=pairs,parse_constant=fail)


def call_model(payload, timeout, phase, *, request_fn=None):
    call = {'phase':phase, 'payload':payload, 'prompt_characters':len(payload['prompt']),
            'format_characters':len(json.dumps(payload['format'],ensure_ascii=False))}
    t = time.perf_counter()
    kind = 'provider'
    try:
        env = (request_fn or request)('/api/generate', payload, timeout)
        call['provider'] = {k:env.get(k) for k in PROVIDER_KEYS}
        call['raw_response'] = env.get('response')
        call['thinking_characters'] = len(env.get('thinking') or '')
        if (env.get('model')!=payload['model'] or env.get('done') is not True
                or env.get('done_reason')=='length' or env.get('thinking')):
            raise ValueError('Invalid/truncated provider output')
        kind = 'schema'
        call['proposal'] = strict(env['response'])
    except (OSError,ValueError,KeyError,TypeError) as exc:
        call['technical_error'] = f'{type(exc).__name__}: {exc}'
        call['failure_kind'] = kind
        call['timeout'] = isinstance(exc,TimeoutError) or isinstance(getattr(exc,'reason',None),TimeoutError)
    finally:
        call['seconds'] = time.perf_counter()-t
    return call


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect disabled')


class QwenClient:
    def __init__(self, config, *, transport=None):
        self.config = config
        self.transport = transport

    def request(self, path, payload=None, timeout=120):
        if self.transport is not None:
            return self.transport(path, payload, timeout)
        raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        with build_opener(ProxyHandler({}), NoRedirect()).open(
            Request(self.config.base_url.rstrip('/') + path, data=raw,
                    headers={'Content-Type': 'application/json'}), timeout=timeout
        ) as response:
            data = response.read(2000001)
        if len(data) > 2000000:
            raise ValueError('Response too large')
        obj = strict(data)
        if not isinstance(obj, dict):
            raise ValueError('Ollama response must be a JSON object')
        if obj.get('error'):
            raise ValueError('Ollama error: ' + str(obj['error']))
        return obj

    def call_model(self, payload, timeout, phase):
        return call_model(payload, timeout, phase, request_fn=self.request)


def request(path, payload=None, timeout=120):
    # Default helper for direct engine use; the service always injects its client.
    from src.grading.config import GradingConfig
    return QwenClient(GradingConfig.from_env()).request(path, payload, timeout)
