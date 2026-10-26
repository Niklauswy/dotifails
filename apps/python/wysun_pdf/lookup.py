"""Explicit, bounded online lookups. No network request is made while selecting text."""
from html.parser import HTMLParser
import json
from urllib.parse import urlencode, quote

from PySide6.QtCore import QObject, Signal, QProcess, QProcessEnvironment, QTimer
from wysun_core import launch


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
        data = payload.get('responseData')
        if not isinstance(data, dict):
            raise ValueError('Respuesta no válida del proveedor.')
        value = data.get('translatedText')
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
    timeout_ms = 15000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.generation, self.process = 0, None

    def command(self):
        return launch.argv('wysun_pdf.lookup_worker')

    def cancel(self):
        self.generation += 1
        process, self.process = self.process, None
        if process:
            process.kill()

    def search(self, kind, text, source='en', target='es'):
        self.cancel()
        try:
            url = request_url(kind, text, source, target)
        except ValueError as error:
            self.failed.emit(str(error))
            return
        token = self.generation
        process = self.process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert('PYTHONPATH', str(launch.ROOT))
        process.setProcessEnvironment(environment)
        timer = QTimer(process, singleShot=True, interval=self.timeout_ms)
        output, errors = bytearray(), []
        reported = False

        def fail(message):
            nonlocal reported
            if token == self.generation and not reported:
                reported = True
                self.failed.emit(message)

        def timeout():
            fail('La consulta tardó demasiado. Puedes volver a intentarlo.')
            process.kill()

        def receive():
            output.extend(bytes(process.readAllStandardOutput()))
            if len(output) > 524288:
                errors.append('Respuesta del proveedor demasiado grande.')
                process.kill()

        def finished(*_):
            timer.stop()
            receive()
            if self.process is process:
                self.process = None
            try:
                if token != self.generation or reported:
                    return
                if errors or process.exitCode() != 0:
                    raise ValueError(errors[0] if errors else 'El proceso de consulta no pudo terminar.')
                reply = json.loads(output.decode('utf-8'))
                if not isinstance(reply, dict):
                    raise ValueError('Respuesta no válida del proceso de consulta.')
                if 'error' in reply:
                    raise ValueError(str(reply['error']))
                self.completed.emit(parse_results(kind, reply.get('result'), text, target))
            except (ValueError, TypeError, AttributeError) as error:
                fail(str(error))
            finally:
                process.deleteLater()

        def process_error(error):
            if error == QProcess.FailedToStart:
                timer.stop()
                if self.process is process:
                    self.process = None
                fail('No se pudo iniciar la consulta.')
                process.deleteLater()

        def started():
            process.write((json.dumps({'url': url}) + '\n').encode())
            process.closeWriteChannel()

        process.started.connect(started)
        process.readyReadStandardOutput.connect(receive)
        process.errorOccurred.connect(process_error)
        process.finished.connect(finished)
        timer.timeout.connect(timeout)
        command = self.command()
        process.start(command[0], command[1:])
        timer.start()
