#!/usr/bin/env python3
"""Wysun Installer: a new installation, maintenance of an existing one, and a side-effect-free tour.

Four moments and one living centrepiece each: who you are (your system), how it will look, what it
brings, and the installation itself. A row of shapes above shows the way; the bar below holds the
next step and turns into a wavy progress line while work runs.
"""
import argparse
import os
from pathlib import Path
import platform
import shlex
import time

from material_widgets import (ActionCard, Button, CheckRow, Crossfade, FlowGrid, Hero, IconButton, InstalledCard,
                              LogView, PageStack, Panel, Sheet, ShortcutRow, StatusMark, WaveBar, apply_style, label,
                              metric, paint_surface, restyle_label, text_font)
from scenes import AddonTile, AppBubble, CoreCard, PillSwitch, RunScene, ScanScene, Stepper
from PySide6.QtCore import QProcess, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from shiboken6 import isValid
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)
from theme_tokens import invalidate, on_theme_changed, refresh_widgets
import theme_core
from icons import icon
from install_model import COMPONENTS, InstallOptions, backups, load_json, preflight, read_os_release
import journey
from process_runner import InstallerProcess
from preview_process import PreviewProcess

HOME, SYSTEM, CONTENT, RUN = range(4)
RESIZE_MARGIN = 6
FACTS = {
    'sudo': 'Autorización con sudo', 'package-health': 'APT y dpkg en orden', 'paths': 'Tus archivos se respaldan',
    'lock': 'Sin otra instalación activa', 'network': 'Necesita Internet',
}


def receipt_at(home):
    value = load_json(Path(home) / '.local/state/dotifails/installed.json', {})
    return value if isinstance(value, dict) else {}


def clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            clear(item.layout())


def fact(check):
    """A check as a few words for a pill; the full explanation stays for problems."""
    key, level, title = check['key'], check['level'], check['title']
    if key == 'space':
        return level, title.replace(' disponibles en el hogar', ' libres en tu carpeta')
    if key == 'system-space':
        return level, title.replace(' disponibles en el sistema', ' libres en el sistema')
    if level == 'ok' and key in FACTS:
        return level, FACTS[key]
    if key == 'network':
        return level, FACTS[key]
    return level, title


class Worker(QThread):
    """Read-only work (checks, plan) off the UI thread; results carry a generation to drop stale ones."""

    ready = Signal(str, int, object)

    def __init__(self, kind, generation, job, parent):
        super().__init__(parent)
        self.kind, self.generation, self.job = kind, generation, job

    def run(self):
        try:
            result = self.job()
        except Exception as error:  # Shown as a check, never as a crash.
            result = error
        self.ready.emit(self.kind, self.generation, result)


class InstallerWindow(QWidget):
    def __init__(self, source, home=None, preview=False):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.source = Path(source).expanduser().resolve()
        bundled = Path(__file__).resolve().parent.parent
        if preview and not (self.source / 'manifests/packages.json').is_file() and (bundled / 'manifests/packages.json').is_file():
            self.source = bundled
        self.home = Path(home or Path.home()).absolute()
        self.preview = preview
        self.receipt = {} if preview else receipt_at(self.home)
        self.updating = not preview and bool(self.receipt.get('components') or
            (self.home / '.local/share/orbit/app/orbit.py').is_file() or
            (self.home / '.local/share/wysun/quickshell/shell.qml').is_file())
        self.fields = read_os_release()
        self.machine = platform.machine()
        previous = set(self.receipt.get('last_selection') or self.receipt.get('components') or journey.ADDONS)
        self.addons = {key for key in journey.ADDONS if key in previous}
        self.page_index, self.furthest = HOME, HOME
        self.generation = {'host': 0, 'review': 0}
        self.operation_kind, self.last_result, self.last_plan, self.checks, self.host = 'install', {}, None, [], []
        self.run_stages = []
        self.operation_ran = False
        self.workers, self.preview_windows = [], []
        self.close_after_work = False
        self.started_at = time.monotonic()
        self.runner = PreviewProcess(self) if preview else InstallerProcess(self.home, self)
        self.runner.line.connect(self.append_log)
        self.runner.event.connect(self.on_event)
        self.runner.finished.connect(self.on_finished)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_elapsed)
        self.review_timer = QTimer(self, singleShot=True, interval=220)
        self.review_timer.timeout.connect(self.refresh_review)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setWindowTitle('Instalador de Wysun' + (' · Vista previa' if preview else ''))
        self.setWindowIcon(icon('download'))
        self.setMinimumSize(820, 600)
        self.resize(1180, 800)
        apply_style(self)
        self.build_frame()
        self.build_home()
        self.build_system()
        self.build_content()
        self.build_run()
        self.show_page(HOME, animate=False)
        on_theme_changed(self.refresh_theme)
        for keys, callback in (('Alt+Left', self.go_back), ('Alt+Right', self.advance), ('Ctrl+Return', self.advance),
                               ('F1', self.show_help), ('Ctrl+L', self.toggle_log), ('Ctrl+Q', self.close)):
            QShortcut(QKeySequence(keys), self).activated.connect(callback)

    # ------------------------------------------------------------------ frame
    def build_frame(self):
        outer = QVBoxLayout(self)
        gap = metric('space_s')
        outer.setContentsMargins(gap, gap, gap, gap)
        outer.setSpacing(gap)
        top = QHBoxLayout()
        top.setContentsMargins(metric('space_xs'), metric('space_xs'), metric('space_xs'), 0)
        side = metric('space_xl') * 6
        left = QHBoxLayout()
        left.setSpacing(metric('space_s'))
        self.close_button = IconButton('close', 'Cerrar · Ctrl+Q', self.close, size=34)
        left.addWidget(self.close_button)
        self.mode_label = label('Vista previa' if self.preview else 'Mantenimiento' if self.updating else 'Instalador', 'eyebrow', False)
        left.addWidget(self.mode_label)
        left.addStretch()
        holder = QWidget()
        holder.setLayout(left)
        holder.setFixedWidth(side)
        top.addWidget(holder)
        self.stepper = Stepper()
        first = ('dashboard', 'Resumen') if self.updating else ('home', 'Inicio')
        last = ('history', 'Actividad') if self.updating else ('download', 'Instalación')
        self.stepper.set_steps([first, ('computer', 'Tu equipo'), ('apps', 'Contenido'), last])
        self.stepper.selected.connect(self.navigate)
        top.addWidget(self.stepper, 1)
        right = QHBoxLayout()
        right.setSpacing(2)
        right.addStretch()
        self.recovery_button = IconButton('history', 'Recuperación', self.show_recovery, size=34)
        self.recovery_button.setVisible(not self.preview)
        self.help_button = IconButton('keyboard', 'Atajos · F1', self.show_help, size=34)
        right.addWidget(self.recovery_button)
        right.addWidget(self.help_button)
        holder = QWidget()
        holder.setLayout(right)
        holder.setFixedWidth(side)
        top.addWidget(holder)
        outer.addLayout(top)
        self.panel = Panel()
        inner = QVBoxLayout(self.panel)
        inner.setContentsMargins(0, 0, 0, 0)
        self.stack = PageStack()
        inner.addWidget(self.stack)
        outer.addWidget(self.panel, 1)
        self.bar = Panel()
        self.bar.setFixedHeight(metric('space_xl') * 3 + metric('space_s'))
        row = QHBoxLayout(self.bar)
        pad = metric('space_l')
        row.setContentsMargins(pad, 0, pad, 0)
        row.setSpacing(metric('space_m'))
        self.bar_mark = StatusMark(metric('space_xl'))
        row.addWidget(self.bar_mark)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addStretch()
        self.bar_title = label('', 'cardTitle', False)
        self.bar_detail = label('', 'small', False)
        for item in (self.bar_title, self.bar_detail):
            item.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            text.addWidget(item)
        text.addStretch()
        row.addLayout(text, 2)
        self.wave = WaveBar()
        self.wave.hide()
        row.addWidget(self.wave, 3)
        self.details_button = Button('Detalles', self.show_details, symbol='expand_less')
        self.stop_button = Button('Detener', self.request_stop, symbol='pause')
        self.back = Button('Atrás', self.go_back, symbol='arrow_back')
        self.next = Button('Comenzar', self.advance, 'primary')
        for button in (self.details_button, self.stop_button, self.back, self.next):
            row.addWidget(button)
        self.stop_button.hide()
        outer.addWidget(self.bar)

    def scroll_page(self, centred=False):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        content.setObjectName('scrollBody')
        layout = QVBoxLayout(content)
        pad = metric('space_xl') + metric('space_s')
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(metric('space_l'))
        layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(content)
        self.stack.add(scroll)
        return layout

    @staticmethod
    def centred(widget, role=None):
        if role:
            widget.setAlignment(Qt.AlignHCenter)
        return widget

    # ------------------------------------------------------------------ pages
    def build_home(self):
        layout = self.scroll_page()
        if self.updating:
            installed = [journey.COMPONENTS[k]['title'] for k in self.receipt.get('components', []) if k in journey.COMPONENTS]
            subtitle = f'{len(installed)} componentes' if installed else 'Componentes por comprobar'
            layout.addWidget(label('Hola de nuevo', 'eyebrow'))
            layout.addWidget(label('Tu Wysun', 'heading'))
            self.installed_card = InstalledCard(self.source, 'Wysun está en este equipo', subtitle + '.\nActualiza las aplicaciones y el shell sin tocar paquetes ni tus datos.')
            self.installed_card.clicked.connect(self.confirm_update)
            layout.addWidget(self.installed_card)
            grid = FlowGrid(metric('space_xl') * 10, maximum_columns=2)
            cards = (('tune', 'Instalación', 'Modificar', 'Añade o quita piezas o actualiza el sistema.', True, self.modify),
                     ('monitoring', 'Comprobar', 'Diagnóstico', 'Revisa dependencias, sesión y archivos instalados.', False, self.run_doctor),
                     ('history', 'Respaldos', 'Recuperación', 'Vuelve a una configuración anterior de Wysun o del arranque.', False, self.show_recovery),
                     ('visibility', 'Vista previa', 'Instalación nueva', 'Recorre la instalación completa sin cambiar nada.', False, self.open_preview))
            for symbol, eyebrow, title, subtitle, accent, callback in cards:
                card = ActionCard(symbol, eyebrow, title, subtitle, accent)
                card.setFixedHeight(metric('space_xl') * 7)
                card.clicked.connect(callback)
                grid.add(card)
            layout.addWidget(grid)
            return
        self.hero = Hero(self.source)
        layout.addWidget(self.hero, 1)
        layout.addSpacing(metric('space_s'))
        row = QHBoxLayout()
        row.setSpacing(metric('space_xl') + metric('space_s'))
        text = QVBoxLayout()
        text.setSpacing(metric('space_s'))
        text.addWidget(label('Para Debian 13 y Parrot 7', 'eyebrow'))
        text.addWidget(label('Un escritorio completo sobre tu sistema.', 'hero'))
        text.addWidget(label('Hyprland, el shell de Wysun y sus aplicaciones, configurados como en el proyecto. '
                             'Tu distribución, tus datos y tus ajustes privados se quedan donde están.', 'body'))
        text.addStretch()
        row.addLayout(text, 5)
        points = QVBoxLayout()
        points.setSpacing(metric('space_m'))
        for symbol, title, detail in (('desktop_windows', 'Escritorio', 'Sesión Wysun / Hyprland con barra, lanzador y Settings.'),
                                      ('library_music', 'Aplicaciones', 'Music, Files, Recorder, capturas con OCR y bloqueo.'),
                                      ('power_settings_new', 'Arranque', 'GRUB, carga y acceso como terminal de refinamiento.')):
            item = QHBoxLayout()
            item.setSpacing(metric('space_m'))
            mark = StatusMark(metric('space_xl') + metric('space_xs'))
            mark.set_level('info', symbol)
            item.addWidget(mark, 0, Qt.AlignTop)
            words = QVBoxLayout()
            words.setSpacing(2)
            words.addWidget(label(title, 'cardTitle'))
            words.addWidget(label(detail, 'small'))
            item.addLayout(words, 1)
            points.addLayout(item)
        row.addLayout(points, 4)
        layout.addLayout(row)

    def build_system(self):
        layout = self.scroll_page()
        self.scan = ScanScene()
        ok = journey.supported(self.fields, self.machine)
        detail = self.machine + ' · Linux ' + platform.release().split('-')[0] + \
            (' · compatible' if ok else ' · Wysun necesita Debian 13 o Parrot 7 en x86_64')
        self.scan.set_system((self.fields.get('ID') or '?')[:1].upper(), journey.system_name(self.fields), detail)
        layout.addWidget(self.scan)
        self.problems = QVBoxLayout()
        self.problems.setSpacing(metric('space_s'))
        layout.addLayout(self.problems)
        row = QHBoxLayout()
        row.addStretch()
        self.upgrade = PillSwitch('Actualizar también el sistema')
        self.upgrade.setChecked(not self.updating)
        self.upgrade.toggled.connect(lambda _on: self.schedule_review())
        row.addWidget(self.upgrade)
        row.addStretch()
        layout.addLayout(row)
        suite = journey.backports_suite(self.fields) or 'backports'
        note = label(f'Con los repositorios de tu distribución, sin retirar paquetes ni cambiar de versión. '
                     f'Si falta, se añade el repositorio oficial {suite}.', 'small')
        note.setAlignment(Qt.AlignHCenter)
        layout.addWidget(note)

    def build_content(self):
        layout = self.scroll_page()
        layout.addWidget(CoreCard())
        layout.addSpacing(metric('space_xs'))
        layout.addWidget(label('Añade si quieres', 'eyebrow'))
        row = QHBoxLayout()
        row.setSpacing(metric('space_m'))
        self.addon_tiles = {}
        for key, (symbol, title, detail, sides) in journey.ADDONS.items():
            tile = AddonTile(symbol, title, detail, sides)
            tile.setChecked(key in self.addons)
            tile.toggled.connect(lambda on, k=key: self.addon_changed(k, on))
            self.addon_tiles[key] = tile
            row.addWidget(tile, 1)
        layout.addLayout(row)
        layout.addSpacing(metric('space_xs'))
        layout.addWidget(label('Aplicaciones · Flatpak', 'eyebrow'))
        apps = QHBoxLayout()
        apps.setSpacing(metric('space_l'))
        self.app_bubbles = {}
        for key, (title, detail, symbol) in journey.EXTRAS.items():
            bubble = AppBubble(symbol, title, detail)
            bubble.toggled.connect(lambda _on: self.schedule_review())
            self.app_bubbles[key] = bubble
            apps.addWidget(bubble)
        apps.addStretch()
        layout.addLayout(apps)

    def build_run(self):
        layout = self.scroll_page()
        self.run_scene = RunScene()
        layout.addWidget(self.run_scene)
        self.run_eyebrow = label('', 'eyebrow')
        self.run_title = label('', 'hero')
        self.run_detail = label('', 'body')
        for item in (self.run_eyebrow, self.run_title, self.run_detail):
            item.setAlignment(Qt.AlignHCenter)
            layout.addWidget(item)
        self.result_box = QVBoxLayout()
        self.result_box.setSpacing(metric('space_m'))
        layout.addLayout(self.result_box)
        logs = QHBoxLayout()
        logs.addStretch()
        self.elapsed = label('00:00', 'small', False)
        logs.addWidget(self.elapsed)
        self.log_toggle = Button('Registro', self.toggle_log, symbol='expand_more')
        logs.addWidget(self.log_toggle)
        logs.addStretch()
        layout.addLayout(logs)
        self.logs = LogView()
        self.logs.setMinimumHeight(metric('space_xl') * 9)
        self.logs.hide()
        layout.addWidget(self.logs)
        self.run_location = label('', 'small')
        self.run_location.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self.run_location)

    # ------------------------------------------------------------------ theme
    def refresh_theme(self):
        if not isValid(self):  # Listeners are weak in Python, not in C++: a closed window may linger.
            return
        for widget in self.findChildren(QLabel):
            role = widget.property('installerRole')
            if role:
                restyle_label(widget, role)
        self.setWindowIcon(icon('download'))
        self.update()

    # ------------------------------------------------------------------ selection
    def addon_changed(self, key, on):
        self.addons.add(key) if on else self.addons.discard(key)
        self.schedule_review()

    def selected_components(self):
        chosen = set(journey.CORE) | self.addons
        return tuple(k for k in COMPONENTS if k in chosen)

    def extras(self):
        return tuple(k for k, bubble in self.app_bubbles.items() if bubble.isChecked())

    def options(self):
        return InstallOptions(self.source, Path.home() if self.preview else self.home, self.selected_components(),
                              self.extras(), ('grub', 'plymouth'),
                              upgrade_system=self.upgrade.isChecked(), prepare_repositories=True)

    def choose_source(self):
        chosen = QFileDialog.getExistingDirectory(self, 'Copia completa del proyecto Wysun', str(self.source))
        if not chosen:
            return
        source = Path(chosen)
        if not (source / 'installer/main.py').is_file() or not (source / 'manifests/packages.json').is_file():
            self.notice('Copia incompleta', 'Elige la raíz del proyecto: la carpeta que contiene installer/, apps/, config/ y manifests/.')
            return
        self.source = source.resolve()
        self.refresh_review()

    # ------------------------------------------------------------------ navigation
    def reachable(self):
        if self.runner.running:
            return {RUN}
        # A preview and an existing installation can be explored freely; a new one goes in order.
        limit = CONTENT if self.preview or self.updating else self.furthest
        pages = set(range(min(limit, CONTENT) + 1))
        if self.operation_ran:
            pages.add(RUN)
        return pages

    def navigate(self, index):
        if index in self.reachable():
            self.show_page(index)

    def go_back(self):
        if self.sheet_open() or self.runner.running:
            return
        if self.page_index == RUN:
            self.show_page(CONTENT if self.operation_kind == 'install' else HOME)
        elif self.page_index > HOME:
            self.show_page(self.page_index - 1)

    def advance(self):
        if self.sheet_open() or self.runner.running or not self.next.isEnabled():
            return
        if self.page_index == CONTENT:
            self.start_install()
        elif self.page_index == RUN:
            self.close()
        elif self.page_index == HOME and self.updating:
            self.modify()
        else:
            self.show_page(self.page_index + 1)

    def modify(self):
        self.show_page(SYSTEM)

    def show_page(self, index, animate=True):
        if not HOME <= index <= RUN:
            return
        direction = 1 if index >= self.page_index else -1
        self.page_index = index
        if index <= CONTENT:
            self.furthest = max(self.furthest, index)
        self.stack.set_current(index, direction, animate)
        self.stepper.set_current(index, self.reachable(), animate)
        if index == SYSTEM and not self.host:
            self.refresh_host()
        if index == CONTENT:
            self.refresh_review()
        self.update_bar()

    def update_bar(self):
        index = self.page_index
        running = self.runner.running
        self.back.setVisible(HOME < index < RUN and not running)
        self.stop_button.setVisible(running and self.operation_kind != 'restore')
        self.next.setVisible(not running)
        self.wave.setVisible(index == RUN and (running or bool(self.last_result)))
        self.recovery_button.setEnabled(not running)
        self.details_button.setVisible(index == CONTENT and bool(self.checks))
        text = {
            HOME: ('Modificar instalación', 'tune') if self.updating else ('Comenzar', 'arrow_forward'),
            CONTENT: ('Simular instalación' if self.preview else 'Instalar', 'download'),
            RUN: ('Cerrar', 'close'),
        }.get(index, ('Continuar', 'arrow_forward'))
        self.next.set_content(text[1], text[0])
        self.next.setEnabled(True)
        title, detail, level = '', '', None
        if index == HOME:
            title, detail = (('Vista previa', 'Recorre la instalación completa: nada se ejecuta ni se escribe') if self.preview else
                             ('Wysun está instalado', 'Actualiza, modifica, diagnostica o recupera') if self.updating else
                             ('Nada cambia todavía', 'Primero miramos tu equipo y eliges cómo será tu Wysun'))
        elif index == SYSTEM:
            blocking = journey.blocking(self.host)
            title = 'Leyendo tu equipo…' if not self.host else 'Hay algo que resolver' if blocking else 'Tu equipo está listo'
            detail = blocking[0]['title'] if blocking else 'Sistema al día al instalar' if self.upgrade.isChecked() else 'Sin actualizar el sistema'
            level = 'active' if not self.host else 'error' if blocking else 'ok'
        elif index == CONTENT:
            pending = self.generation_pending('review') or self.review_timer.isActive()
            blocking = journey.blocking(self.checks)
            ready = bool(self.last_plan) and not blocking and not pending
            title = journey.selection_title(self.selected_components(), self.extras())
            detail = ('Comprobando…' if pending else blocking[0]['title'] if blocking else
                      journey.summary_line(self.last_plan) if self.last_plan else '')
            level = 'active' if pending else 'error' if blocking else 'ok' if ready else None
            self.next.setEnabled(ready)
        elif index == RUN:
            title, detail = self.bar_status
            level = self.bar_level
        self.bar_title.setText(title)
        self.bar_detail.setText(detail)
        self.bar_mark.setVisible(level is not None)
        if level:
            self.bar_mark.set_level(level)

    bar_status = ('', '')
    bar_level = None

    # ------------------------------------------------------------------ checks
    def generation_pending(self, kind):
        return any(worker.kind == kind and worker.generation == self.generation[kind] for worker in self.workers)

    def launch(self, kind, job):
        self.generation[kind] += 1
        worker = Worker(kind, self.generation[kind], job, self)
        self.workers.append(worker)
        worker.ready.connect(self.work_ready)
        worker.finished.connect(lambda w=worker: self.work_done(w))
        worker.start()

    def work_done(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()
        if isValid(self):
            self.update_bar()
        if self.close_after_work and not self.workers:
            self.close()

    def work_ready(self, kind, generation, result):
        if generation != self.generation[kind]:
            return
        if kind == 'host':
            self.render_host(result)
        else:
            self.render_review(result)

    def refresh_host(self):
        self.host = []
        clear(self.problems)
        self.scan.scanning()
        if self.preview:
            QTimer.singleShot(1400, lambda: isValid(self) and self.render_host(journey.preview_checks(self.fields, self.machine)))
        else:
            options = InstallOptions(self.source, self.home, ('terminal',))

            def job():
                checks = preflight(options)
                return journey.host_checks(checks) or checks
            self.launch('host', job)
        self.update_bar()

    def render_host(self, result):
        if isinstance(result, Exception):
            result = [dict(key='system', level='error', title='No se pudo comprobar el equipo', detail=str(result))]
        self.host = result
        facts = [fact(check) for check in result if check['key'] not in ('system', 'apt-get', 'apt-cache', 'dpkg-query')
                 or check['level'] == 'error']
        blocking = journey.blocking(result)
        state = 'error' if blocking else 'warning' if any(c['level'] == 'warning' for c in result) else 'ok'
        self.scan.set_facts(facts, state)
        clear(self.problems)
        for check in result:
            if check['level'] in ('error', 'warning'):
                self.problems.addWidget(CheckRow(check))
        self.update_bar()

    def schedule_review(self):
        self.review_timer.start()
        self.update_bar()

    def refresh_review(self):
        self.review_timer.stop()
        options = self.options()
        if self.preview:
            def job():
                plan = options.summary(preview=True)
                return [dict(key='preview', level='info', title='Recorrido de demostración',
                             detail='Las comprobaciones y el progreso son un ejemplo. No se ejecutan comandos.')], plan
        else:
            def job():
                try:
                    options.validate()
                except ValueError as error:
                    return [dict(key='options', level='error', title='Revisa la selección', detail=str(error))], {}
                checks = preflight(options)
                return checks, (options.summary() if not journey.blocking(checks) else {})
        self.launch('review', job)
        self.update_bar()

    def render_review(self, result):
        if isinstance(result, Exception):
            result = [dict(key='review', level='error', title='No se pudo completar la revisión', detail=str(result))], {}
        self.checks, self.last_plan = result
        self.update_bar()

    def show_details(self):
        sheet = Sheet(self, 'Antes de instalar', metric('space_xl') * 26)
        for check in self.checks:
            if check['level'] != 'ok':
                sheet.body.addWidget(CheckRow(check))
        plan = self.last_plan
        if plan:
            stages = journey.phases(plan, batcat=True if self.preview else None)
            sheet.body.addWidget(label(f'{len(stages)} etapas · ' + ' → '.join(s['name'] for s in stages), 'small'))
            view = LogView()
            view.setAccessibleName('Detalles técnicos')
            view.setPlainText(shlex.join(['/usr/bin/python3', str(self.source / 'installer/main.py'), *plan['command']]) +
                              f'\n\nPaquetes APT ({len(plan["packages"])}):\n' + (' '.join(plan['packages']) or '—'))
            view.setMinimumHeight(metric('space_xl') * 7)
            sheet.body.addWidget(view)
        sheet.body.addWidget(label('Origen: ' + str(self.source), 'small'))
        row = self.sheet_buttons(sheet, ('Cerrar', sheet.close_sheet, 'primary'))
        row.insertWidget(0, Button('Cambiar origen', lambda: (sheet.close_sheet(), self.choose_source()), symbol='folder_open'))
        sheet.open()

    # ------------------------------------------------------------------ operations
    def start_install(self):
        if self.runner.running:
            return
        options = self.options()
        try:
            plan = options.summary(preview=self.preview)
        except (ValueError, OSError, KeyError):
            self.show_page(CONTENT)
            return
        if not self.preview and (not self.last_plan or plan != self.last_plan or journey.blocking(self.checks)):
            self.show_page(CONTENT)
            return
        self.last_plan = plan
        self.start_operation('install', '/usr/bin/python3', [str(self.source / 'installer/main.py'), *options.argv()], plan)

    def start_operation(self, kind, program, arguments, plan=None):
        if self.runner.running:
            return
        self.operation_kind, self.last_result = kind, {}
        self.operation_ran = True
        clear(self.result_box)
        self.logs.clear()
        stages = (journey.phases(plan, batcat=True if self.preview else None) if kind == 'install' and plan else
                  journey.update_phases() if kind == 'update' else [])
        self.run_stages = [dict(name=stage['name'], symbol=stage['symbol'], detail=stage['detail'], level='pending') for stage in stages]
        self.set_log_visible(not stages)
        eyebrow = {'install': 'Simulación' if self.preview else 'Instalando', 'update': 'Actualizando',
                   'doctor': 'Diagnóstico', 'restore': 'Recuperación'}[kind]
        self.run_eyebrow.setText(eyebrow.upper())
        self.run_title.setText({'install': 'Preparando…', 'update': 'Actualizando Wysun', 'doctor': 'Comprobando el entorno',
                                'restore': 'Recuperando la configuración'}[kind])
        self.run_detail.setText('Simulación en memoria: no se ejecuta nada.' if self.preview else
                                'Se pedirá tu contraseña cuando haga falta preparar el sistema.' if kind == 'install' else
                                'Espera a que termine.')
        self.run_scene.start(len(stages), 'download' if kind == 'install' else 'sync')
        self.bar_status = (eyebrow + '…', 'Puedes detenerla entre etapas' if kind != 'restore' else 'No cierres la ventana')
        self.bar_level = 'active'
        self.stop_button.setEnabled(True)
        self.stop_button.set_content('pause', 'Detener')
        self.wave.set_progress(None if not stages else 0.0, True)
        self.started_at = time.monotonic()
        try:
            self.runner.start(program, arguments, self.source, plan)
        except (OSError, ValueError, RuntimeError) as error:
            self.show_page(RUN)
            self.on_finished(1, dict(status='failed', message=str(error)))
            return
        self.show_page(RUN)
        self.run_location.setText('' if self.preview else 'Registro privado: ' + str(self.runner.directory / 'console.log'))
        self.timer.start()
        self.update_elapsed()
        self.update_bar()

    def run_stage(self, name, index=None):
        names = [stage['name'] for stage in self.run_stages]
        if name not in names:
            from journey import phase
            entry = dict(phase(name), level='pending')
            self.run_stages.insert(min(len(self.run_stages), index if index is not None else len(self.run_stages)), entry)
            names = [stage['name'] for stage in self.run_stages]
        return names.index(name), self.run_stages[names.index(name)]

    def append_log(self, text):
        self.logs.appendPlainText(text)

    def on_event(self, event):
        kind = event.get('event')
        if kind == 'phase':
            position, stage = self.run_stage(event['name'], event.get('index'))
            for earlier in self.run_stages[:position]:
                if earlier['level'] in ('pending', 'active'):
                    earlier['level'] = 'done' if earlier['level'] == 'active' else 'skipped'
            stage['level'] = 'active'
            total = len(self.run_stages)
            self.run_scene.stage(position, total, stage['symbol'])
            self.run_title.setText(event['name'])
            self.run_detail.setText(stage.get('detail') or '')
            self.wave.set_progress(position / max(1, total), True)
            self.bar_status = (event['name'], f'Etapa {position + 1} de {total}')
            self.update_bar()
        elif kind == 'phase_done':
            if event.get('name'):
                position, stage = self.run_stage(event['name'])
                stage['level'] = 'done'
                self.run_scene.advance_dots(position + 1)
                self.wave.set_progress((position + 1) / max(1, len(self.run_stages)), True)
        elif kind == 'operation':
            self.run_detail.setText(event['name'])
        elif kind == 'backup':
            self.append_log('Respaldo creado: ' + event['id'])
        elif kind == 'system_backup':
            self.append_log('Respaldo del arranque: ' + event['id'])
        elif kind == 'conflict':
            self.append_log('Cambio personal conservado: ' + event['path'])
        elif kind == 'error':
            self.append_log(event['message'])

    def update_elapsed(self):
        seconds = int(time.monotonic() - self.started_at)
        self.elapsed.setText(f'{seconds // 60:02d}:{seconds % 60:02d}')

    def toggle_log(self):
        if self.page_index != RUN and self.operation_ran:
            self.show_page(RUN)
        self.set_log_visible(not self.logs.isVisible())

    def set_log_visible(self, visible):
        self.logs.setVisible(visible)
        self.log_toggle.set_content('expand_less' if visible else 'expand_more', 'Ocultar registro' if visible else 'Registro')

    def request_stop(self):
        if not self.runner.running:
            return
        self.runner.cancel()
        self.stop_button.setEnabled(False)
        self.stop_button.set_content('pause', 'Deteniendo…')
        self.bar_status = ('Deteniendo…', 'Se completará la etapa en curso antes de parar')
        self.update_bar()

    def on_finished(self, code, result):
        self.timer.stop()
        self.last_result = result
        state = result.get('status', 'failed')
        kind = self.operation_kind
        level = {'complete': 'done', 'conflicts': 'warning', 'cancelled': 'cancelled'}.get(state, 'error')
        if kind == 'doctor' and code:
            level = 'warning'
        for stage in self.run_stages:
            if stage['level'] == 'active':
                stage['level'] = level
        self.run_scene.finish(level)
        self.wave.set_progress(1.0 if state in ('complete', 'conflicts') else self.wave.value or 0.0, False)
        title, detail = self.result_copy(kind, state, code)
        self.run_eyebrow.setText({'done': 'Terminado', 'warning': 'Terminado con avisos', 'cancelled': 'Detenido',
                                  'error': 'Sin completar'}[level].upper())
        self.run_title.setText(title)
        self.run_detail.setText(detail)
        self.bar_status = (title, journey.summary_line(self.last_plan) if kind == 'install' and self.last_plan else detail)
        self.bar_level = {'done': 'ok'}.get(level, level)
        self.build_result(kind, state, result)
        if level == 'error' or kind == 'doctor':
            self.set_log_visible(True)
        if self.page_index != RUN:
            self.show_page(RUN)
        self.stepper.set_current(self.page_index, self.reachable(), False)
        self.update_bar()

    def result_copy(self, kind, state, code):
        if kind == 'doctor':
            return ('Todo en orden', 'El diagnóstico no encontró problemas.') if code == 0 else \
                ('Hay puntos que revisar', 'El registro indica qué falta y cómo resolverlo.')
        if kind == 'restore':
            return ('Configuración recuperada', 'Las ediciones posteriores se guardaron aparte. Los paquetes siguen instalados.') \
                if state == 'complete' else ('La recuperación necesita atención', 'Consulta el registro antes de volver a intentarlo.')
        if self.preview and state == 'complete':
            return 'Así se instala Wysun', 'Todo fue simulado: tu equipo no cambió.'
        return {
            'complete': ('Wysun está listo' if kind == 'install' else 'Wysun está al día',
                         'Cada etapa terminó y se verificó.' if kind == 'install' else 'Aplicaciones, shell y runtime actualizados.'),
            'conflicts': ('Listo, con tus cambios a salvo', 'Algunos archivos tenían ediciones tuyas: se conservaron y la versión nueva quedó aparte.'),
            'cancelled': ('Instalación detenida', 'Se detuvo entre etapas. Lo que se cambió tiene respaldo.'),
        }.get(state, ('Hay una etapa que resolver', 'La operación no terminó. El registro muestra la causa; los archivos cambiados tienen respaldo.'))

    def build_result(self, kind, state, result):
        clear(self.result_box)
        if result.get('message'):
            self.result_box.addWidget(CheckRow(dict(level='error', title='Motivo', detail=result['message'])))
        if result.get('conflicts'):
            backup = self.home / '.local/state/dotifails/backups' / str(result.get('backup', ''))
            self.result_box.addWidget(CheckRow(dict(level='warning', title=f"{len(result['conflicts'])} archivos con cambios tuyos",
                detail='Revisa las versiones nuevas en ' + str(backup / 'incoming') + ':\n' + '\n'.join(result['conflicts'][:12]))))
        plan = self.last_plan or {}
        actions = QHBoxLayout()
        actions.setSpacing(metric('space_s'))
        actions.addStretch()
        shortcuts = None
        if state == 'complete' and kind == 'install' and 'wayland' in plan.get('components', []):
            steps = 'Reinicia cuando quieras y elige «Wysun / Hyprland» en tu pantalla de acceso. Tu sesión actual sigue siendo la predeterminada.'
            if 'boot' in plan.get('components', []):
                steps += ' El arranque será una terminal de refinamiento.'
            note = label(steps, 'body')
            note.setAlignment(Qt.AlignHCenter)
            self.result_box.addWidget(note)
            actions.addWidget(Button('Reiniciar ahora…', self.reboot, 'primary', symbol='restart_alt'))
            shortcuts = FlowGrid(metric('space_xl') * 9, maximum_columns=3)
            for keys, action in journey.SHORTCUTS:
                shortcuts.add(ShortcutRow(keys, action))
        if state in ('failed', 'cancelled', 'conflicts') or kind == 'doctor':
            if not self.preview:
                actions.addWidget(Button('Recuperación', self.show_recovery, symbol='history'))
            if kind == 'install':
                actions.addWidget(Button('Volver a elegir', lambda: self.show_page(CONTENT), symbol='arrow_back'))
        actions.addStretch()
        self.result_box.addLayout(actions)
        if shortcuts is not None:
            self.result_box.addSpacing(metric('space_s'))
            heading = label('Tus primeros atajos', 'eyebrow')
            heading.setAlignment(Qt.AlignHCenter)
            self.result_box.addWidget(heading)
            self.result_box.addWidget(shortcuts)
        if result.get('backup') and not self.preview:
            backup = label('Respaldo de esta operación: ' + str(result['backup']), 'small')
            backup.setAlignment(Qt.AlignHCenter)
            self.result_box.addWidget(backup)

    def confirm_update(self):
        sheet = Sheet(self, 'Actualizar Wysun')
        sheet.body.addWidget(label('Copia la versión actual de las aplicaciones, el shell, Recorder y el runtime desde ' +
                                   str(self.source) + '.', 'body'))
        sheet.body.addWidget(label('No instala paquetes ni cambia atajos, notas, historial o colores. Si editaste un '
                                   'archivo de Wysun, tu versión se conserva y la nueva queda aparte.', 'small'))
        self.sheet_buttons(sheet, ('Cancelar', sheet.close_sheet, ''),
                           ('Actualizar', lambda: (sheet.close_sheet(), self.update_applications()), 'primary'))
        sheet.open()

    def update_applications(self):
        self.last_plan = {'components': ['desktop'], 'config_only': True}
        self.start_operation('update', '/usr/bin/python3', [str(self.source / 'installer/main.py'), 'install', '--source',
            str(self.source), '--target-home', str(self.home), '--wysun-only'], self.last_plan)

    def run_doctor(self):
        self.start_operation('doctor', '/usr/bin/python3', [str(Path(__file__).with_name('main.py')), 'doctor', '--target-home', str(self.home)])

    def open_preview(self):
        window = InstallerWindow(self.source, self.home, preview=True)
        self.preview_windows.append(window)
        window.show()

    def reboot(self):
        sheet = Sheet(self, 'Reiniciar el equipo')
        if self.preview:
            sheet.body.addWidget(label('En la vista previa no se reinicia nada. En una instalación real, esto pediría '
                                       'el reinicio al sistema después de confirmarlo.', 'body'))
            self.sheet_buttons(sheet, ('Entendido', sheet.close_sheet, 'primary'))
        else:
            sheet.body.addWidget(label('Guarda tus documentos antes de continuar. Después del reinicio, elige «Wysun / Hyprland» '
                                       'en la pantalla de acceso.', 'body'))
            self.sheet_buttons(sheet, ('Ahora no', sheet.close_sheet, ''),
                               ('Reiniciar', lambda: (sheet.close_sheet(), self.request_reboot()), 'primary'))
        sheet.open()

    def request_reboot(self):
        if self.preview:
            return
        if not QProcess.startDetached('systemctl', ['reboot'])[0]:
            self.notice('No se pudo pedir el reinicio', 'Reinicia desde el menú de sesión cuando hayas guardado tu trabajo.')

    # ------------------------------------------------------------------ sheets
    def sheet_open(self):
        return any(isinstance(child, Sheet) and child.isVisible() and not child.closing for child in self.children())

    @staticmethod
    def sheet_buttons(sheet, *buttons):
        row = QHBoxLayout()
        row.setSpacing(metric('space_s'))
        row.addStretch()
        for text, callback, role in buttons:
            symbol = {'Restaurar': 'history', 'Reiniciar': 'restart_alt'}.get(text, 'check' if role == 'primary' else 'close')
            row.addWidget(Button(text, callback, role, symbol=symbol))
        sheet.body.addSpacing(metric('space_xs'))
        sheet.body.addLayout(row)
        return row

    def notice(self, title, text):
        sheet = Sheet(self, title)
        sheet.body.addWidget(label(text, 'body'))
        self.sheet_buttons(sheet, ('Entendido', sheet.close_sheet, 'primary'))
        return sheet.open()

    def show_help(self):
        sheet = Sheet(self, 'Atajos', metric('space_xl') * 22)
        sheet.body.addWidget(label('En este instalador', 'eyebrow'))
        for keys, action in ((('Alt', '→'), 'Continuar'), (('Alt', '←'), 'Volver'), (('Ctrl', 'Enter'), 'Acción principal'),
                             (('Ctrl', 'L'), 'Mostrar u ocultar el registro'), (('Tab',), 'Recorrer los controles'),
                             (('Espacio',), 'Elegir la opción enfocada'), (('Esc',), 'Cerrar esta hoja')):
            sheet.body.addWidget(ShortcutRow(keys, action))
        sheet.body.addWidget(label('En Wysun', 'eyebrow'))
        for keys, action in journey.SHORTCUTS:
            sheet.body.addWidget(ShortcutRow(keys, action))
        self.sheet_buttons(sheet, ('Entendido', sheet.close_sheet, 'primary'))
        sheet.open()

    def show_recovery(self):
        if self.runner.running:
            return
        sheet = Sheet(self, 'Recuperación', metric('space_xl') * 24)
        sheet.body.addWidget(label('Devuelve los archivos que cambió una operación. Las ediciones posteriores se guardan '
                                   'aparte; los paquetes y las actualizaciones del sistema permanecen.', 'body'))
        items = [] if self.preview else backups(self.home)
        listing = QListWidget()
        listing.setAccessibleName('Respaldos de configuraciones')
        listing.setMinimumHeight(metric('space_xl') * 7)
        for item in items:
            stamp = time.strftime('%d/%m/%Y %H:%M', time.localtime(item['created_at']))
            status = {'complete': 'completa', 'restored': 'ya recuperada', 'cancelled': 'detenida',
                      'failed': 'con error'}.get(item['status'], item['status'])
            listing.addItem(f"{stamp} · {status} · {item['operations']} cambios\n{item['id']}")
        if items:
            sheet.body.addWidget(listing)
            sheet.body.addWidget(label('Se recupera del más reciente al más antiguo: elige el primero sin recuperar.', 'small'))
        else:
            listing.hide()
            sheet.body.addWidget(label('La vista previa no accede a tus respaldos.' if self.preview else
                                       'Todavía no hay respaldos. Aparecerán aquí después de instalar o actualizar.', 'small'))
        latest = next((i for i, item in enumerate(items) if item['status'] != 'restored'), None)
        row = QHBoxLayout()
        row.setSpacing(metric('space_s'))
        if not self.preview:
            def boot():
                from boot_recovery import BootRecoveryDialog
                BootRecoveryDialog(self.home, self).exec()
            row.addWidget(Button('Arranque…', boot, symbol='power_settings_new'))
        row.addStretch()
        row.addWidget(Button('Cerrar', sheet.close_sheet, symbol='close'))
        restore = Button('Restaurar', role='primary', symbol='history')
        restore.setEnabled(False)
        row.addWidget(restore)
        listing.currentRowChanged.connect(lambda index: restore.setEnabled(latest is not None and index == latest))

        def apply():
            index = listing.currentRow()
            if self.preview or latest is None or index != latest:
                return
            item = items[index]
            sheet.close_sheet()
            self.start_operation('restore', '/usr/bin/python3', [str(Path(__file__).with_name('main.py')), 'restore', item['id'],
                                                                 '--target-home', str(self.home)])
        restore.clicked.connect(apply)
        sheet.body.addSpacing(metric('space_xs'))
        sheet.body.addLayout(row)
        if latest is not None:
            listing.setCurrentRow(latest)
        sheet.open()

    # ------------------------------------------------------------------ window
    def resizeEvent(self, event):
        self.mode_label.setVisible(self.width() >= 1000)
        super().resizeEvent(event)

    def paintEvent(self, _event):
        paint_surface(self)

    def _edges(self, point):
        edges = Qt.Edges()
        if point.x() <= RESIZE_MARGIN:
            edges |= Qt.LeftEdge
        if point.x() >= self.width() - RESIZE_MARGIN:
            edges |= Qt.RightEdge
        if point.y() <= RESIZE_MARGIN:
            edges |= Qt.TopEdge
        if point.y() >= self.height() - RESIZE_MARGIN:
            edges |= Qt.BottomEdge
        return edges

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.windowHandle() is None:
            return
        edges = self._edges(event.position().toPoint())
        if edges:
            self.windowHandle().startSystemResize(edges)
        else:
            self.windowHandle().startSystemMove()

    def mouseMoveEvent(self, event):
        edges = self._edges(event.position().toPoint())
        shapes = {Qt.LeftEdge: Qt.SizeHorCursor, Qt.RightEdge: Qt.SizeHorCursor, Qt.TopEdge: Qt.SizeVerCursor,
                  Qt.BottomEdge: Qt.SizeVerCursor}
        if edges in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges in shapes:
            self.setCursor(shapes[edges])
        else:
            self.unsetCursor()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and not self.sheet_open():
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.runner.running:
            event.ignore()
            if self.operation_kind == 'restore':
                self.notice('Recuperación en curso', 'Espera a que termine la recuperación antes de cerrar.')
            elif not self.runner.cancel_requested and not self.sheet_open():
                sheet = Sheet(self, 'La operación sigue en curso')
                sheet.body.addWidget(label('Puedes detenerla: terminará la etapa actual y se conservará el respaldo. '
                                           'APT, la compilación y el arranque no se interrumpen a la fuerza.', 'body'))
                self.sheet_buttons(sheet, ('Seguir', sheet.close_sheet, ''),
                                   ('Detener', lambda: (sheet.close_sheet(), self.request_stop()), 'primary'))
                sheet.open()
            return
        if any(worker.isRunning() for worker in self.workers):
            self.close_after_work = True
            event.ignore()
            self.hide()
            return
        for key in self.generation:
            self.generation[key] += 1
        event.accept()


def launch(source=None, home=None, preview=False):
    home = Path(home or Path.home())
    previous = receipt_at(home).get('source')
    source = Path(source or previous or Path(__file__).resolve().parent.parent)
    app = QApplication.instance() or QApplication(['wysun-installer'])
    app.setApplicationName('wysun-installer')
    app.setApplicationDisplayName('Instalador de Wysun')
    app.setDesktopFileName('wysun-installer-preview' if preview else 'dotifails-installer')
    app.setOrganizationName('Wysun')
    app.setStyle('Fusion')
    window = InstallerWindow(source, home, preview=preview)
    # Following the desktop's appearance is read-only. The shared app watcher migrates old theme
    # files, which would break the preview's no-write contract, so this polls instead.
    window.theme_revision = theme_core.visual_key()
    window.theme_watcher = QTimer(window)
    window.theme_watcher.setInterval(500)

    def refresh_appearance():
        revision = theme_core.visual_key()
        if revision != window.theme_revision:
            window.theme_revision = revision
            invalidate()
            refresh_widgets()
    window.theme_watcher.timeout.connect(refresh_appearance)
    window.theme_watcher.start()
    app.setFont(text_font())
    geometry = app.primaryScreen().availableGeometry()
    window.resize(min(1180, geometry.width() - metric('space_xl') * 2), min(800, geometry.height() - metric('space_xl') * 2))
    window.show()
    return app.exec()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Instalador de Wysun')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    raise SystemExit(launch(args.source, preview=args.preview))
