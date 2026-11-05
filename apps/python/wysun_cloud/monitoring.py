"""CPU history for one VM from Cloud Monitoring.

The access token comes from ``gcloud auth print-access-token`` right before each
request, travels only in the ``Authorization`` header over HTTPS to
``monitoring.googleapis.com``, and is never written, cached, logged or included
in an error message. Only the resulting ``(epoch, 0..1)`` points are cached, for
five minutes, keyed by project, zone, name and range.
"""
from datetime import datetime
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from wysun_cloud.gcloud import GcloudError

API = 'https://monitoring.googleapis.com'
TIMEOUT = 15
CACHE_SECONDS = 300
MAX_PAGES = 5
METRIC = 'compute.googleapis.com/instance/cpu/utilization'

# key -> (saved_at, [(epoch, 0..1), ...]); results only, never the token.
_cache = {}


def clear_cache():
    """Forget every cached history (tests, or an explicit refresh)."""
    _cache.clear()


def _rfc3339(seconds):
    """A UTC timestamp in the RFC3339 form Cloud Monitoring expects."""
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(seconds))


def _alignment(hours):
    """One point every five minutes for a day, every hour for a week."""
    return '3600s' if hours > 24 else '300s'


def _error_status(body):
    """Only the short ``error.status`` of an error body, never the rest of it."""
    try:
        data = json.loads((body or b'').decode('utf-8', 'replace'))
    except (AttributeError, ValueError):
        return ''
    error = data.get('error') if isinstance(data, dict) else None
    status = error.get('status') if isinstance(error, dict) else None
    if not isinstance(status, str):
        return ''
    return ''.join(char for char in status if char.isalnum() or char in '_.-')[:40]


def _fetch(url, token):
    """One GET with the token in the header; failures become short Spanish messages."""
    request = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }, method='GET')
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        try:
            detail = _error_status(error.read())
        except OSError:
            detail = ''
        message = f'Monitoring respondió {error.code}'
        raise GcloudError(f'{message}: {detail}' if detail else message) from None
    except (urllib.error.URLError, OSError):
        raise GcloudError('Monitoring no respondió') from None
    try:
        return json.loads(body)
    except (TypeError, ValueError):
        raise GcloudError('Monitoring devolvió una respuesta ilegible') from None


def _points(answer):
    """The ``(epoch, 0..1)`` points of an answer, clamped and unsorted."""
    found = []
    series = answer.get('timeSeries') if isinstance(answer, dict) else None
    for item in series or []:
        for point in item.get('points') or []:
            when = (point.get('interval') or {}).get('endTime')
            value = point.get('value') or {}
            number = value.get('doubleValue')
            if number is None and value.get('int64Value') is not None:
                number = value.get('int64Value')
            if not isinstance(when, str) or not when or number is None:
                continue
            try:
                stamp = datetime.fromisoformat(when.replace('Z', '+00:00')).timestamp()
                fraction = float(number)
            except (TypeError, ValueError):
                continue
            found.append((stamp, min(1.0, max(0.0, fraction))))
    return found


def cpu_history(gcloud, inst, hours):
    """The CPU utilisation of ``inst`` over the last ``hours``, oldest first."""
    key = (inst.project, inst.zone, inst.name, hours)
    now = time.time()
    cached = _cache.get(key)
    if cached is not None and now - cached[0] < CACHE_SECONDS:
        return list(cached[1])

    token = gcloud.token()
    params = {
        'filter': f'metric.type="{METRIC}" AND metric.labels.instance_name="{inst.name}"',
        'interval.startTime': _rfc3339(now - hours * 3600),
        'interval.endTime': _rfc3339(now),
        'aggregation.alignmentPeriod': _alignment(hours),
        'aggregation.perSeriesAligner': 'ALIGN_MEAN',
        'aggregation.crossSeriesReducer': 'REDUCE_MEAN',
    }
    project = urllib.parse.quote(inst.project, safe='')
    points = []
    page_token = ''
    for _ in range(MAX_PAGES):
        query = dict(params)
        if page_token:
            query['pageToken'] = page_token
        url = f'{API}/v3/projects/{project}/timeSeries?{urllib.parse.urlencode(query)}'
        answer = _fetch(url, token)
        points.extend(_points(answer))
        page_token = answer.get('nextPageToken') if isinstance(answer, dict) else ''
        if not page_token:
            break
    points.sort(key=lambda point: point[0])
    _cache[key] = (now, points)
    return list(points)
