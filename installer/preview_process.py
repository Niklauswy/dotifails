"""In-memory demo transport. Never starts a subprocess, asks for privileges or creates a directory.

It walks the same stages ``main.py install`` would run for the plan (journey.phases), with the
same event vocabulary, so the preview shows the real timeline without touching the machine.
"""
from PySide6.QtCore import QObject, QTimer, Signal

from journey import phases

OPERATIONS = {
    'Repositorios oficiales de la distribución': ('Leyendo las fuentes de APT', 'Comprobando las claves oficiales'),
    'Índices APT y compatibilidad de dependencias': ('Descargando índices', 'Simulando la resolución de dependencias'),
    'Actualización del sistema': ('Calculando la actualización', 'Actualizando paquetes sin retiradas'),
    'Paquetes del sistema': ('Resolviendo dependencias', 'Instalando paquetes'),
    'Herramientas verificadas': ('Descargando herramientas fijadas', 'Comprobando sumas SHA-256'),
    'Configuraciones y respaldos': ('Creando el respaldo', 'Copiando Wysun y sus dotfiles', 'Preparando el runtime de Qt y Quickshell'),
    'Registrar sesión Wysun / Hyprland': ('Añadiendo la sesión al gestor de acceso',),
    'Arranque y acceso': ('Respaldando GRUB y Plymouth', 'Aplicando Blue CRT', 'Comprobando la configuración generada'),
    'Lenguajes y plugins de Neovim': ('Instalando plugins', 'Preparando lenguajes'),
    'Aplicaciones opcionales': ('Instalando aplicaciones Flatpak',),
    'Caché de terminal': ('Reconstruyendo la caché',),
    'Fuentes del escritorio': ('Actualizando la caché de fuentes',),
    'Verificación final': ('Comprobando cada componente',),
}


class PreviewProcess(QObject):
    line = Signal(str)
    event = Signal(dict)
    finished = Signal(int, dict)
    started = Signal()
    directory = None

    def __init__(self, parent=None, interval=420):
        super().__init__(parent)
        self.running = False
        self.cancel_requested = False
        self.timer = QTimer(self)
        self.timer.setInterval(interval)
        self.timer.timeout.connect(self.tick)
        self.steps = []

    def start(self, program, arguments, source, plan=None):
        if self.running:
            raise RuntimeError('La demostración ya está en curso.')
        self.running, self.cancel_requested = True, False
        names = [item['name'] for item in phases(plan or {}, batcat=True)]
        self.total = len(names)
        # A flat script of (kind, payload) events, consumed one per tick.
        self.steps = []
        for index, name in enumerate(names):
            self.steps.append(('phase', dict(event='phase', name=name, index=index, total=self.total)))
            if name == 'Configuraciones y respaldos':
                self.steps.append(('event', dict(event='backup', id='vista-previa', path='')))
            for operation in OPERATIONS.get(name, ()):
                self.steps.append(('operation', dict(event='operation', name=operation)))
            self.steps.append(('event', dict(event='phase_done', name=name, index=index + 1, total=self.total)))
        self.started.emit()
        self.line.emit('VISTA PREVIA · Todo el proceso es simulado; no se ejecutan comandos.')
        self.tick()
        self.timer.start()

    def tick(self):
        if self.cancel_requested and self.steps and self.steps[0][0] == 'phase' or not self.steps:
            self.timer.stop()
            self.running = False
            status = 'cancelled' if self.cancel_requested and self.steps else 'complete'
            self.finished.emit(130 if status == 'cancelled' else 0,
                               {'status': status, 'preview': True, 'backup': 'vista-previa'})
            return
        kind, payload = self.steps.pop(0)
        self.event.emit(payload)
        if kind == 'phase':
            self.line.emit('\n→ ' + payload['name'])
        elif kind == 'operation':
            self.line.emit('  Simulación: ' + payload['name'])

    def cancel(self):
        if self.running and not self.cancel_requested:
            self.cancel_requested = True
            self.line.emit('Detención solicitada. Se completará la etapa en curso.')
