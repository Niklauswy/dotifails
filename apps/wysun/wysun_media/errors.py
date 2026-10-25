"""Stable error vocabulary shared by sessions, image loaders and the widgets."""
from dataclasses import dataclass

MESSAGES = {
    'missing': 'No se encuentra el archivo.',
    'unsupported': 'El formato de este archivo no es compatible.',
    'rejected': 'Solo se pueden abrir archivos locales.',
    'unreadable': 'No se pudo leer el archivo.',
    'decode': 'No se pudo decodificar el contenido.',
    'too_large': 'La imagen es demasiado grande para mostrarla de forma segura.',
    'audio': 'No se pudo iniciar la salida de audio.',
    'render': 'No se pudo preparar la salida de video.',
    'backend': 'Falta libmpv o no se pudo iniciar. Comprueba su instalación.',
    'nothing': 'El archivo no contiene audio ni video reproducibles.',
}


@dataclass(frozen=True)
class MediaError(Exception):
    """``category`` is stable; ``operation`` names what failed ('open', 'seek', 'track'…)."""
    category: str
    operation: str = 'open'
    detail: str = ''
    recoverable: bool = False

    def __str__(self):
        return self.message

    @property
    def message(self):
        return MESSAGES.get(self.category, 'No se pudo reproducir el archivo.')
