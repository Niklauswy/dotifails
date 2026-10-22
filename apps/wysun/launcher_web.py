"""Bounded, cookie-free webpage metadata previews. No scripts or remote HTML rendering."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
import ipaddress
import socket
import hashlib
import json
import os
import time
from pathlib import Path


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Unsupported address')
    addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80))
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Local address')
    return url


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, public_url(newurl))


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values, self.title, self.in_title = {}, '', False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'meta':
            key = (attrs.get('property') or attrs.get('name') or '').lower()
            if key not in self.values:
                self.values[key] = attrs.get('content', '')[:2000]

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title = (self.title + data)[:500]


def fetch(url, limit, types):
    opener = build_opener(ProxyHandler({}), Redirects())
    request = Request(public_url(url), headers={'User-Agent': 'Wysun-LinkPreview/1.0', 'Accept': ', '.join(types)})
    with opener.open(request, timeout=3) as response:
        mime = response.headers.get_content_type()
        if mime not in types:
            raise ValueError('Unsupported content')
        data = b''
        html = mime in ('text/html', 'application/xhtml+xml')
        while len(data) <= limit:
            chunk = response.read1(min(16384, limit + 1 - len(data)))
            if not chunk:
                break
            data += chunk
            if html and b'</head' in data.lower():
                break
        if len(data) > limit and not html:
            raise ValueError('Preview too large')
        return data, response.geturl(), response.headers.get_content_charset() or 'utf-8', mime


def preview(url, on_metadata=None):
    result = {'url': url, 'domain': urlsplit(url).hostname or url, 'title': '', 'description': '', 'image': ''}
    try:
        data, final, charset, _ = fetch(url, 512 * 1024, ('text/html', 'application/xhtml+xml'))
        parser = Metadata()
        parser.feed(data.decode(charset, errors='replace'))
        values = parser.values
        result.update(title=(values.get('og:title') or values.get('twitter:title') or parser.title).strip(),
                      description=(values.get('og:description') or values.get('description') or '').strip()[:500])
        result['status'] = 'loading-image'
        if on_metadata:
            on_metadata(dict(result))
        image = values.get('og:image') or values.get('twitter:image')
        if image:
            import base64
            data, _, _, mime = fetch(urljoin(final, image), 3 * 1024 * 1024, ('image/png', 'image/jpeg', 'image/webp'))
            result['image'] = 'data:' + mime + ';base64,' + base64.b64encode(data).decode()
        result['status'] = 'ready'
    except (OSError, ValueError, LookupError):
        result['status'] = 'unavailable'
    return result


def cached_preview(url, on_metadata=None):
    """Private, bounded local cache; no URL is sent to a third-party screenshot service."""
    folder = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'wysun/link-previews'
    key = hashlib.sha256(url.encode()).hexdigest()
    target = folder / (key + '.json')
    try:
        saved = json.loads(target.read_text())
        ttl = 3600 if saved.get('status') == 'ready' else 60
        if time.time() - target.stat().st_mtime < ttl and saved.get('url') == url:
            return saved
    except (OSError, ValueError):
        pass
    result = preview(url, on_metadata)
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = target.with_suffix('.' + str(os.getpid()) + '.tmp')
        with temporary.open('w') as stream:
            os.chmod(temporary, 0o600)
            json.dump(result, stream)
        temporary.replace(target)
        for old in sorted(folder.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[32:]:
            old.unlink(missing_ok=True)
    except OSError:
        pass
    return result
