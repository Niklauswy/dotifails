"""Optional local OCR. Uses installed Tesseract/languages only, never downloads."""
import shutil
import subprocess
from .storage import image_bytes


def available():return shutil.which('tesseract') is not None


def recognize(image,language='eng',timeout=30):
    executable=shutil.which('tesseract')
    if not executable:raise RuntimeError('OCR opcional: instala Tesseract y sus idiomas localmente')
    if not language or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+' for c in language):
        raise ValueError('Invalid OCR language')
    result=subprocess.run([executable,'stdin','stdout','-l',language],input=image_bytes(image),capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('OCR local no disponible para el idioma seleccionado: '+result.stderr.decode(errors='replace')[:600])
    return result.stdout.decode('utf8',errors='replace').strip()
