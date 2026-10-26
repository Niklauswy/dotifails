"""One bounded HTTPS request in a disposable process; no Qt networking dependency."""
import json
import sys
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_RESPONSE = 65536
HOSTS = {'api.mymemory.translated.net', 'en.wikipedia.org', 'es.wikipedia.org'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, opener=None):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError('Dirección del proveedor no permitida.')
    request = Request(url, headers={'User-Agent': 'WysunPDF/1.0 (local study reader)', 'Accept': 'application/json'})
    opener = opener or build_opener(NoRedirect())
    with opener.open(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError('El servicio no está disponible en este momento.')
        body = response.read(MAX_RESPONSE + 1)
    if len(body) > MAX_RESPONSE:
        raise ValueError('La respuesta del proveedor supera el límite permitido.')
    return json.loads(body.decode('utf-8'))


def main():
    try:
        request = json.loads(sys.stdin.buffer.readline(8193))
        result = {'result': fetch(request['url'])}
    except Exception:
        # Neither the query URL nor provider tracebacks belong in logs/UI.
        result = {'error': 'No se pudo consultar el servicio. Comprueba la conexión o inténtalo más tarde.'}
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
