"""Provider service status from public Statuspage summaries (no credentials)."""
import importlib.util
from pathlib import Path

PAGES = {
    'claude': ('status.claude.com', ('claude.ai', 'Claude Code', 'Claude API (api.anthropic.com)',
                                     'Claude Console (platform.claude.com)')),
    'codex': ('status.openai.com', ('ChatGPT', 'Codex', 'API', 'APIs')),
}
INDICATORS = {'none', 'minor', 'major', 'critical', 'maintenance'}


def _credentials():
    spec = importlib.util.spec_from_file_location('wysun_ai_usage_credentials', Path(__file__).with_name('credentials.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


credentials = _credentials()


def fetch(provider, opener=None):
    """{indicator, description, components:[{name,status}], url}; indicator 'unknown' when it cannot be read."""
    page = PAGES.get(provider)
    if not page:
        return {'indicator': 'unknown', 'description': None, 'components': [], 'url': None}
    host, wanted = page
    url = f'https://{host}'
    status, body = credentials.get_json(f'{url}/api/v2/summary.json', {}, frozenset({host}), opener=opener)
    if status != 200 or not isinstance(body, dict):
        return {'indicator': 'unknown', 'description': None, 'components': [], 'url': url}
    overall = body.get('status') or {}
    indicator = overall.get('indicator') if overall.get('indicator') in INDICATORS else 'unknown'
    incidents = [i for i in body.get('incidents') or [] if isinstance(i, dict) and i.get('status') != 'resolved']
    description = incidents[0].get('name') if incidents else overall.get('description')
    components = [c for c in body.get('components') or [] if isinstance(c, dict) and not c.get('group')]
    chosen = [{'name': c.get('name'), 'status': c.get('status')} for c in components if c.get('name') in wanted]
    if not chosen:
        chosen = [{'name': c.get('name'), 'status': c.get('status')} for c in components if not c.get('group_id')][:4]
    return {'indicator': indicator, 'description': description, 'components': chosen, 'url': url}
