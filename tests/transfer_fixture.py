#!/usr/bin/env python3
"""Disposable file share for browser checks. No home data is exposed."""
import json
from pathlib import Path
import signal
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'apps/tools'))
from orbit_tools.transfer import TransferServer
with tempfile.TemporaryDirectory(prefix='orbit-transfer-ui-') as temp:
    root=Path(temp);share=root/'share';share.mkdir();inbox=root/'inbox';inbox.mkdir()
    (share/'Diseño').mkdir();(share/'Diseño/boceto.txt').write_text('fixture')
    (share/'Proyecto.zip').write_bytes(b'x'*32000)
    (share/'Notas.md').write_text('Archivo de prueba.')
    (share/'paisaje.jpg').write_bytes(b'fixture')
    (share/'archivo-con-un-nombre-muy-largo-para-revisar-el-diseño-y-el-desbordamiento.txt').write_text('fixture')
    (share/'<script>alert(1)</script>.txt'.replace('/','_')).write_text('fixture')
    (share/'.env').write_text('not-shared')
    server=TransferServer(('127.0.0.1',0),share,uploads=inbox,max_bytes=1024*1024,quiet=True)
    def stop(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','inbox':str(inbox)}),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
