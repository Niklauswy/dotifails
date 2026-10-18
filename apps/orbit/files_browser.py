"""Open local PDFs with the configured browser, without shell interpolation."""
import os,subprocess
from pathlib import Path

def browser_command(path):
    result=subprocess.run(['xdg-settings','get','default-web-browser'],capture_output=True,text=True,timeout=3,check=True)
    desktop=result.stdout.strip()
    if not desktop or Path(desktop).name!=desktop:raise RuntimeError('No hay un navegador predeterminado válido.')
    roots=[os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share'))]+os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':')
    for root in roots:
        entry=Path(root)/'applications'/desktop
        if entry.is_file():return ['gio','launch',str(entry),Path(path).absolute().as_uri()]
    raise RuntimeError('No se encontró el navegador predeterminado.')

def open_pdf(path):
    subprocess.Popen(browser_command(path),start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
