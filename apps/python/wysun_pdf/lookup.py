"""Explicit, bounded online lookups. No network request is made while selecting text."""
from html.parser import HTMLParser
import json
from urllib.parse import urlencode, quote

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class PlainText(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(value)

    def handle_data(self, data):
        self.parts.append(data)


def request_url(kind, text, source='en', target='es'):
    text = text.strip()
    if source not in ('en', 'es') or target not in ('en', 'es'):
        raise ValueError('Elige inglés o español.')
    if not text:
        raise ValueError('Escribe una palabra o un concepto.')
    if kind == 'translation':
        if len(text.encode('utf-8')) > 500 or '\n\n' in text:
            raise ValueError('Selecciona una palabra o un fragmento corto: máximo 500 bytes, un párrafo.')
        return 'https://api.mymemory.translated.net/get?' + urlencode({'q': text, 'langpair': source+'|'+target})
    if kind != 'concept' or len(text) > 160:
        raise ValueError('Busca un concepto de hasta 160 caracteres.')
    return f'https://{target}.wikipedia.org/w/rest.php/v1/search/page?' + urlencode({'q': text, 'limit': 3})


def parse_results(kind, payload, text, target):
    if not isinstance(payload, dict):
        raise ValueError('Respuesta no válida del proveedor.')
    if kind == 'translation':
        if str(payload.get('responseStatus')) != '200':
            raise ValueError('MyMemory no pudo traducir: servicio o cuota no disponible. Inténtalo más tarde.')
        value = payload.get('responseData', {}).get('translatedText')
        if not isinstance(value, str) or not value.strip():
            return []
        return [dict(title=text, body=value, source='MyMemory · Translated',
                     url='https://mymemory.translated.net/', attribution='Traducción orientativa · MyMemory')]
    pages = payload.get('pages')
    if not isinstance(pages, list):
        raise ValueError('Wikipedia no devolvió una lista de referencias.')
    results = []
    for page in pages[:3]:
        if not isinstance(page, dict) or not isinstance(page.get('key'), str):
            continue
        title = str(page.get('title') or page['key'])
        body = ''.join(PlainText(str(page.get('excerpt') or page.get('description') or '')).parts)
        results.append(dict(title=title, body=body, source=f'Wikipedia · {target.upper()}',
                            url=f'https://{target}.wikipedia.org/wiki/' + quote(page['key'], safe=''),
                            attribution='Fragmento de Wikipedia · CC BY-SA · autores e historial en la fuente'))
    return results


class LookupClient(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.generation, self.reply = 0, None

    def cancel(self):
        self.generation += 1
        reply, self.reply = self.reply, None
        if reply:
            reply.abort()

    def search(self, kind, text, source='en', target='es'):
        self.cancel()
        try:
            url = request_url(kind, text, source, target)
        except ValueError as error:
            self.failed.emit(str(error))
            return
        token = self.generation
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b'User-Agent', b'WysunPDF/1.0 (local study reader)')
        request.setTransferTimeout(15000)
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.ManualRedirectPolicy)
        reply = self.reply = self.manager.get(request)
        reply.setReadBufferSize(65537)
        buffer, error_message = bytearray(), []

        def receive():
            buffer.extend(bytes(reply.readAll()))
            if len(buffer) > 65536:
                error_message.append('La respuesta del proveedor supera el límite permitido.')
                reply.abort()

        def finished():
            if token != self.generation:
                reply.deleteLater()
                return
            self.reply = None
            receive()
            try:
                if error_message:
                    raise ValueError(error_message[0])
                if reply.error() != QNetworkReply.NoError:
                    raise ValueError('No se pudo consultar el servicio. Comprueba la conexión o inténtalo más tarde.')
                if reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) != 200:
                    raise ValueError('El servicio no está disponible en este momento.')
                payload = json.loads(buffer.decode('utf-8'))
                self.completed.emit(parse_results(kind, payload, text, target))
            except (ValueError, TypeError, AttributeError) as error:
                self.failed.emit(str(error))
            finally:
                reply.deleteLater()
        reply.readyRead.connect(receive)
        reply.finished.connect(finished)
