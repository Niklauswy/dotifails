#!/usr/bin/env python3
"""Wysun's native installation, update and recovery experience."""
import argparse
import json
from pathlib import Path
import shlex
import sys
import time

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QDialog, QFileDialog,
    QFrame, QHBoxLayout, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from install_model import (BOOT_COMPONENTS, COMPONENTS, THEMES, InstallOptions, backups,
                           load_json, normalize_components, preflight)
from process_runner import InstallerProcess
from visual_widgets import STYLE, Button, ChoiceCard, DesktopPreview, label, reveal

THEME_NAMES = {'severance':'Severance', 'tokyo':'Tokyo', 'space-black':'Space Black'}
THEME_COPY = {'severance':'Azules tranquilos y acentos suaves.', 'tokyo':'Contraste nocturno, violeta y neón.', 'space-black':'Negros profundos y luz contenida.'}
STEPS = ('Bienvenida', 'Apariencia', 'Componentes', 'Opciones', 'Revisión', 'Instalación', 'Primeros pasos')


def surface(layout, role='surface'):
    frame = QFrame()
    frame.setObjectName(role)
    inner = QVBoxLayout(frame)
    inner.setContentsMargins(20, 18, 20, 18)
    inner.setSpacing(12)
    layout.addWidget(frame)
    return inner


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


class InstallerWindow(QMainWindow):
    def __init__(self, source, home=None):
        super().__init__()
        self.source = Path(source).resolve()
        self.home = Path(home or Path.home()).absolute()
        self.receipt = load_json(self.home / '.local/state/dotifails/installed.json', {})
        self.updating = bool(self.receipt)
        current = load_json(self.home / '.config/orbit/theme.json', {}).get('id') or self.receipt.get('theme', 'severance')
        self.theme = {'azul':'severance', 'morado':'tokyo'}.get(current, current)
        if self.theme not in THEMES:
            self.theme = 'severance'
        self.selected = set(self.receipt.get('last_selection', COMPONENTS)) & COMPONENTS.keys()
        self.selected = set(normalize_components(self.selected or None))
        self.page_index = 0
        self.furthest = 0
        self.operation_kind = 'install'
        self.last_result = {}
        self.last_plan = None
        self.checks = []
        self.cancel_pending = False
        self.runner = InstallerProcess(self.home, self)
        self.runner.line.connect(self.append_log)
        self.runner.event.connect(self.on_event)
        self.runner.finished.connect(self.on_finished)
        self.setWindowTitle('Instalador de Wysun')
        self.setWindowFlag(Qt.Dialog, True)
        self.setWindowIcon(QIcon(str(self.source / 'apps/orbit/orbit.png')))
        self.setMinimumSize(780, 580)
        self.resize(1100, 780)
        self.setStyleSheet(STYLE)
        self.build_shell()
        self.build_welcome()
        self.build_themes()
        self.build_components()
        self.build_options()
        self.build_review()
        self.build_progress()
        self.build_finish()
        self.sync_components()
        self.show_page(0, animate=False)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_elapsed)

    def build_shell(self):
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        self.sidebar = QWidget()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setFixedWidth(205)
        nav = QVBoxLayout(self.sidebar)
        nav.setContentsMargins(20, 30, 20, 22)
        nav.setSpacing(6)
        nav.addWidget(label('Ó R B I T A', 'section', False))
        nav.addWidget(label('INSTALADOR', 'eyebrow'))
        nav.addSpacing(32)
        self.nav_buttons = []
        for index, title in enumerate(STEPS):
            button = Button(f'{index+1:02d}   {title}', lambda checked=False, i=index: self.navigate(i), 'nav')
            button.setCheckable(True)
            nav.addWidget(button)
            self.nav_buttons.append(button)
        nav.addStretch(1)
        self.backups_button = Button('Respaldos', self.show_backups, 'quiet')
        self.help_button = Button('Primeros pasos', self.show_guide, 'quiet')
        nav.addWidget(self.backups_button)
        nav.addWidget(self.help_button)
        nav.addSpacing(16)
        nav.addWidget(label('dotifails  /  Linux X11\nDebian 13 · Parrot 7', 'small'))
        shell.addWidget(self.sidebar)
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.stack = QStackedWidget()
        column.addWidget(self.stack, 1)
        footer = QFrame()
        footer.setObjectName('footer')
        controls = QHBoxLayout(footer)
        controls.setContentsMargins(28, 18, 28, 18)
        self.footer_note = label('', 'small')
        controls.addWidget(self.footer_note, 1)
        self.back = Button('Atrás', lambda: self.show_page(self.page_index-1))
        self.next = Button('Empezar  →', self.advance, 'primary')
        controls.addWidget(self.back)
        controls.addWidget(self.next)
        column.addWidget(footer)
        shell.addWidget(body, 1)

    def page(self, eyebrow, heading, description, hero=False):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName('scrollBody')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 30, 32, 28)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)
        layout.addWidget(label(eyebrow, 'eyebrow'))
        layout.addWidget(label(heading, 'hero' if hero else 'heading'))
        layout.addWidget(label(description))
        scroll.setWidget(content)
        self.stack.addWidget(scroll)
        return layout

    def build_welcome(self):
        layout = self.page('BIENVENIDO A WYSUN', 'Un lugar para\nhacerlo tuyo.',
            'Prepara tu escritorio, elige su aspecto y empieza a trabajar. Cada cambio, acompañado de su respaldo.', True)
        self.welcome_preview = DesktopPreview(self.source, self.theme)
        self.welcome_preview.setMinimumHeight(240)
        layout.addWidget(self.welcome_preview)
        layout.addWidget(label('Vista orientativa con el fondo real del perfil seleccionado.', 'small'))
        row = QHBoxLayout()
        for title, description in (('01  Elige', 'Tema y herramientas.'), ('02  Revisa', 'Un plan antes de instalar.'), ('03  Estrena', 'Tu sesión, cuando decidas.')):
            col = QVBoxLayout()
            col.addWidget(label(title, 'section'))
            col.addWidget(label(description, 'small'))
            row.addLayout(col, 1)
        layout.addLayout(row)
        if self.updating:
            info = surface(layout, 'subtle')
            info.addWidget(label('Ya tienes una instalación de Wysun', 'cardTitle'))
            info.addWidget(label('Usaremos esta copia del proyecto para actualizar lo que elijas. Los archivos personalizados se conservan y se señalan al finalizar.'))
        self.source_label = label('Proyecto: ' + str(self.source), 'small')
        self.source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.source_label)
        row = QHBoxLayout()
        row.addWidget(Button('Elegir otra carpeta…', self.choose_source))
        row.addStretch()
        layout.addLayout(row)

    def build_themes(self):
        layout = self.page('01 / EL AMBIENTE', 'Empieza por cómo se siente.',
            'Tres perfiles coordinados para los paneles, las ventanas, la terminal y el escritorio.')
        self.theme_preview = DesktopPreview(self.source, self.theme)
        self.theme_preview.setMinimumHeight(240)
        layout.addWidget(self.theme_preview)
        layout.addWidget(label('Vista orientativa. El arranque Blue CRT se elige por separado.', 'small'))
        choices = QHBoxLayout()
        choices.setSpacing(12)
        self.theme_cards = {}
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        for key in THEMES:
            card = ChoiceCard(THEME_NAMES[key], THEME_COPY[key])
            card.setMinimumWidth(0)
            card.box.setContentsMargins(15, 18, 35, 18)
            self.theme_group.addButton(card)
            card.setChecked(key == self.theme)
            card.clicked.connect(lambda checked=False, k=key: self.select_theme(k))
            choices.addWidget(card, 1)
            self.theme_cards[key] = card
        layout.addLayout(choices)
        self.preserve_theme = QCheckBox('Conservar el tema y el fondo que uso actualmente')
        self.preserve_theme.setChecked(self.updating)
        self.preserve_theme.setVisible(self.updating)
        layout.addWidget(self.preserve_theme)

    def build_components(self):
        layout = self.page('02 / LO QUE NECESITAS', 'Tu instalación. A tu medida.',
            'Elige qué preparar. Desmarcar un componente conserva su instalación actual.')
        row = QHBoxLayout()
        row.addWidget(Button('Completa', lambda: self.preset('complete')))
        row.addWidget(Button('Esencial', lambda: self.preset('essential')))
        row.addStretch()
        self.component_count = label('', 'small')
        row.addWidget(self.component_count)
        layout.addLayout(row)
        self.component_cards = {}
        for key, (title, description) in COMPONENTS.items():
            card = ChoiceCard(title, description)
            card.setChecked(key in self.selected)
            card.clicked.connect(lambda checked, k=key: self.component_changed(k, checked))
            self.component_cards[key] = card
            layout.addWidget(card)
        self.dependency_note = label('El escritorio y Neovim utilizan Ghostty; al elegirlos se incluye Terminal y shell.', 'small')
        layout.addWidget(self.dependency_note)
        self.config_only = QCheckBox('Solo copiar configuraciones · dependencias ya instaladas')
        self.config_only.setToolTip('Omite APT, descargas, arranque y registro de sesión. Conserva los respaldos de archivos.')
        self.config_only.toggled.connect(self.config_mode_changed)
        layout.addWidget(self.config_only)

    def build_options(self):
        layout = self.page('03 / LOS ÚLTIMOS DETALLES', 'Un poco más tuyo.',
            'Añade tus aplicaciones habituales y decide qué pantallas de arranque cambiar.')
        layout.addWidget(label('Aplicaciones opcionales', 'section'))
        self.extra_cards = {}
        for key, title, description in (('brave','Brave','Navegador · Flatpak para tu usuario'), ('discord','Discord','Comunidades y llamadas · Flatpak para tu usuario'), ('obsidian','Obsidian','Notas y conocimiento · Flatpak para tu usuario')):
            card = ChoiceCard(title, description)
            self.extra_cards[key] = card
            layout.addWidget(card)
        layout.addWidget(label('Arranque Blue CRT', 'section'))
        box = surface(layout, 'subtle')
        self.boot_checks = {}
        for key, title in BOOT_COMPONENTS.items():
            checkbox = QCheckBox(title)
            checkbox.setChecked(True)
            self.boot_checks[key] = checkbox
            box.addWidget(checkbox)
        box.addWidget(label('Se aplican las pantallas compatibles con tu equipo. Los cambios aparecerán en el próximo inicio.', 'small'))
        self.skip_nvim = QCheckBox('Preparar los lenguajes de Neovim en otra ocasión')
        self.skip_nvim.setToolTip('Instala el editor y su configuración; omite la preparación inicial de plugins, LSP y depuradores.')
        layout.addWidget(self.skip_nvim)
        self.samsung = QCheckBox('Perfil específico: Samsung con pantalla táctil defectuosa')
        self.samsung.setToolTip('Desactiva la entrada táctil mediante el perfil existente. Úsalo solo en el equipo que lo necesita.')
        layout.addWidget(self.samsung)

    def build_review(self):
        layout = self.page('04 / TODO A LA VISTA', 'Revisa antes de continuar.',
            'Este es el plan para tu equipo. La instalación empieza al pulsar el botón de abajo.')
        self.review_summary = surface(layout)
        self.check_box = QVBoxLayout()
        self.check_box.setSpacing(12)
        layout.addLayout(self.check_box)
        row = QHBoxLayout()
        row.addWidget(Button('Volver a comprobar', self.refresh_review))
        row.addWidget(Button('Ver plan detallado', self.toggle_plan))
        row.addStretch()
        layout.addLayout(row)
        self.plan_view = QPlainTextEdit()
        self.plan_view.setReadOnly(True)
        self.plan_view.setMinimumHeight(210)
        self.plan_view.setVisible(False)
        self.plan_view.setAccessibleName('Paquetes, herramientas y comando de instalación')
        layout.addWidget(self.plan_view)
        info = surface(layout, 'subtle')
        info.addWidget(label('Tu trabajo tiene respaldo', 'cardTitle'))
        info.addWidget(label('Los archivos se respaldan antes de reemplazarlos. Las ediciones personales se conservan y las nuevas versiones quedan disponibles para revisar. Los paquetes instalados permanecen al restaurar configuraciones.'))

    def build_progress(self):
        layout = self.page('05 / EN MARCHA', 'Preparando tu espacio.',
            'Puedes seguir cada etapa y consultar el registro mientras el instalador trabaja.')
        box = surface(layout)
        self.progress_title = label('Preparando instalación…', 'section')
        box.addWidget(self.progress_title)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        box.addWidget(self.progress)
        row = QHBoxLayout()
        self.phase_count = label('Esperando al instalador', 'small')
        self.elapsed = label('00:00', 'small', False)
        row.addWidget(self.phase_count, 1)
        row.addWidget(self.elapsed)
        box.addLayout(row)
        self.operation_label = label('')
        box.addWidget(self.operation_label)
        self.backup_label = label('El respaldo se crea antes de cambiar los archivos.', 'small')
        layout.addWidget(self.backup_label)
        row = QHBoxLayout()
        self.log_toggle = Button('Ocultar registro', self.toggle_log)
        self.cancel_button = Button('Detener después de esta operación', self.request_stop, 'danger')
        row.addWidget(self.log_toggle)
        row.addStretch()
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(2500)
        self.logs.setMinimumHeight(230)
        self.logs.setAccessibleName('Registro de instalación en tiempo real')
        layout.addWidget(self.logs)
        self.run_location = label('', 'small')
        self.run_location.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.run_location)

    def build_finish(self):
        self.finish_layout = self.page('06 / A PARTIR DE AQUÍ', 'Tu siguiente paso.',
            'El resultado de la operación y las opciones para continuar aparecerán aquí.')
        self.result_box = QVBoxLayout()
        self.finish_layout.addLayout(self.result_box)

    def choose_source(self):
        chosen = QFileDialog.getExistingDirectory(self, 'Carpeta del proyecto dotifails', str(self.source))
        if not chosen:
            return
        source = Path(chosen)
        if not (source / 'installer/main.py').is_file() or not (source / 'manifests/themes.json').is_file():
            QMessageBox.warning(self, 'Carpeta incompleta', 'Elige la raíz del proyecto, que contiene installer/ y manifests/.')
            return
        self.source = source
        self.source_label.setText('Proyecto: ' + str(source))
        for preview in (self.theme_preview, self.welcome_preview):
            preview.source = source
            preview.set_theme(self.theme)

    def select_theme(self, key):
        self.theme = key
        self.preserve_theme.setChecked(False)
        self.theme_preview.set_theme(key)
        self.welcome_preview.set_theme(key)

    def preset(self, key):
        self.selected = set(COMPONENTS) if key == 'complete' else {'desktop', 'terminal', 'boot'}
        if self.config_only.isChecked():
            self.selected.discard('boot')
        self.sync_components()

    def component_changed(self, key, checked):
        if checked:
            self.selected.add(key)
        else:
            self.selected.discard(key)
        if self.selected & {'desktop', 'editor'}:
            self.selected.add('terminal')
        self.sync_components()

    def config_mode_changed(self, checked):
        if checked:
            self.selected.discard('boot')
            for card in self.extra_cards.values():
                card.setChecked(False)
        self.sync_components()

    def sync_components(self):
        terminal_required = bool(self.selected & {'desktop', 'editor'})
        for key, card in self.component_cards.items():
            card.setChecked(key in self.selected)
            card.setEnabled(not (key == 'terminal' and terminal_required) and not (key == 'boot' and self.config_only.isChecked()))
        self.component_cards['terminal'].description.setText('Incluida con el escritorio y Neovim: Ghostty, Zsh, Starship y mise.' if terminal_required else COMPONENTS['terminal'][1])
        self.component_count.setText(f'{len(self.selected)} componentes')
        for checkbox in self.boot_checks.values():
            checkbox.setEnabled('boot' in self.selected)
        for card in self.extra_cards.values():
            card.setEnabled(not self.config_only.isChecked())
        self.skip_nvim.setEnabled('editor' in self.selected and not self.config_only.isChecked())
        self.samsung.setEnabled('desktop' in self.selected)
        if 'desktop' not in self.selected:
            self.samsung.setChecked(False)
        if self.page_index == 2:
            self.next.setEnabled(bool(self.selected))

    def options(self):
        return InstallOptions(self.source, self.home, tuple(key for key in COMPONENTS if key in self.selected),
            None if self.preserve_theme.isChecked() else self.theme,
            tuple(key for key, card in self.extra_cards.items() if card.isChecked()),
            tuple(key for key, checkbox in self.boot_checks.items() if checkbox.isChecked()),
            self.config_only.isChecked(), self.skip_nvim.isChecked(),
            'samsung-touchscreen' if self.samsung.isChecked() else None)

    def navigate(self, index):
        if self.runner.running or index > min(self.furthest, 4):
            return
        self.show_page(index)

    def show_page(self, index, animate=True):
        self.page_index = index
        self.furthest = max(self.furthest, index)
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
            button.setEnabled(not self.runner.running and i <= min(self.furthest, 4))
        self.back.setVisible(0 < index < 5)
        self.next.setVisible(index != 5)
        self.next.setEnabled(True)
        self.next.setText('Empezar  →' if index == 0 else ('Actualizar esta selección' if self.updating else 'Instalar esta selección') if index == 4 else 'Cerrar' if index == 6 else 'Continuar  →')
        self.footer_note.setText('Elige y revisa antes de instalar' if index < 4 else 'Respaldo automático · tu sesión sigue abierta' if index == 4 else 'Operación en curso' if index == 5 else 'Tu sesión sigue abierta')
        self.backups_button.setEnabled(not self.runner.running)
        if index == 2:
            self.sync_components()
        if index == 4:
            self.refresh_review()
        if animate:
            reveal(self.stack.currentWidget())

    def advance(self):
        if self.page_index == 4:
            self.start_install()
        elif self.page_index == 6:
            self.close()
        else:
            self.show_page(self.page_index+1)

    def refresh_review(self):
        clear_layout(self.review_summary)
        clear_layout(self.check_box)
        options = self.options()
        self.checks = preflight(options)
        self.review_summary.addWidget(label('Actualizar selección' if self.updating else 'Nueva instalación', 'section'))
        components = ' · '.join(COMPONENTS[key][0] for key in options.components)
        self.review_summary.addWidget(label(components or 'Elige al menos un componente.'))
        theme_name = 'Conservar el actual' if options.theme is None else THEME_NAMES[options.theme]
        self.review_summary.addWidget(label('Tema: ' + theme_name + '    /    ' + ('Solo configuraciones' if options.config_only else 'Configuración y dependencias'), 'small'))
        self.review_summary.addWidget(label('Aplicaciones: ' + (', '.join(options.extras) or 'Ninguna adicional'), 'small'))
        self.review_summary.addWidget(label('Destino: ' + str(options.home), 'small'))
        if 'boot' in options.components:
            self.review_summary.addWidget(label('Arranque: ' + ', '.join(BOOT_COMPONENTS[key] for key in options.boot_components), 'small'))
        for check in self.checks:
            row = QHBoxLayout()
            marker = {'ok':'✓', 'warning':'!', 'error':'×', 'info':'·'}[check['level']]
            role = {'ok':'success', 'warning':'warning', 'error':'error', 'info':'body'}[check['level']]
            mark = label(marker, role, False)
            mark.setFixedWidth(20)
            row.addWidget(mark, 0, Qt.AlignTop)
            text = QVBoxLayout()
            text.setSpacing(3)
            text.addWidget(label(check['title'], role))
            text.addWidget(label(check['detail'], 'small'))
            row.addLayout(text, 1)
            self.check_box.addLayout(row)
        ready = not any(check['level'] == 'error' for check in self.checks)
        self.next.setEnabled(ready)
        self.footer_note.setText('Todo listo para continuar' if ready else 'Resuelve los puntos señalados para continuar')
        try:
            summary = options.summary()
            text = 'Comando equivalente\n' + shlex.join(['python3', str(self.source/'installer/main.py'), *summary['command']])
            text += '\n\nPaquetes del sistema\n' + (', '.join(summary['packages']) or 'No se instalarán paquetes.')
            text += '\n\nHerramientas verificadas\n' + ('\n'.join(f'{key}  {value}' for key, value in summary['artifacts'].items()) or 'No se descargarán herramientas.')
            self.plan_view.setPlainText(text)
        except ValueError as error:
            self.plan_view.setPlainText(str(error))

    def toggle_plan(self):
        self.plan_view.setVisible(not self.plan_view.isVisible())

    def start_install(self):
        self.refresh_review()
        if any(check['level'] == 'error' for check in self.checks):
            return
        options = self.options()
        self.last_plan = options.summary()
        self.start_operation('install', '/usr/bin/python3', [str(self.source/'installer/main.py'), *options.argv()], self.last_plan)

    def start_operation(self, kind, program, arguments, plan=None):
        self.operation_kind = kind
        self.last_result = {}
        self.logs.clear()
        self.logs.setVisible(True)
        self.log_toggle.setText('Ocultar registro')
        self.cancel_button.setEnabled(True)
        self.cancel_button.setVisible(kind in ('install', 'doctor'))
        self.cancel_button.setText('Detener después de esta operación')
        self.progress.setRange(0, 0)
        self.phase_count.setText('Esperando al proceso')
        self.progress_title.setText({'install':'Preparando instalación…', 'restore':'Restaurando configuración…', 'doctor':'Comprobando la instalación…'}[kind])
        self.operation_label.setText('La autorización del sistema se solicitará cuando sea necesaria.')
        self.backup_label.setText('Los archivos personalizados se conservan.')
        self.started_at = time.monotonic()
        try:
            self.runner.start(program, arguments, self.source, plan)
        except (OSError, ValueError, RuntimeError) as error:
            QMessageBox.warning(self, 'No se pudo iniciar', str(error))
            return
        self.run_location.setText('Registro privado: ' + str(self.runner.directory/'console.log'))
        self.timer.start()
        self.update_elapsed()
        self.show_page(5)

    def append_log(self, text):
        self.logs.appendPlainText(text)

    def on_event(self, event):
        kind = event.get('event')
        if kind == 'phase':
            self.progress.setRange(0, max(1, event['total']))
            self.progress.setValue(event['index'])
            self.progress_title.setText(event['name'])
            self.phase_count.setText(f"Etapa {event['index']+1} de {event['total']} · progreso por etapas")
        elif kind == 'phase_done':
            self.progress.setRange(0, max(1, event['total']))
            self.progress.setValue(event['index'])
        elif kind == 'operation':
            self.operation_label.setText(event['name'])
        elif kind == 'backup':
            self.backup_label.setText('Respaldo: ' + event['id'])
        elif kind == 'system_backup':
            self.append_log('Respaldo del arranque: '+event['id'])
        elif kind == 'conflict':
            self.append_log('Cambio personal conservado: ' + event['path'])
        elif kind == 'error':
            self.append_log(event['message'])

    def update_elapsed(self):
        seconds = int(time.monotonic()-self.started_at)
        self.elapsed.setText(f'{seconds//60:02d}:{seconds%60:02d}')

    def toggle_log(self):
        self.logs.setVisible(not self.logs.isVisible())
        self.log_toggle.setText('Ocultar registro' if self.logs.isVisible() else 'Mostrar registro')

    def request_stop(self):
        self.runner.cancel()
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText('Esperando a que termine la operación…')
        self.footer_note.setText('La operación actual terminará antes de detenerse')

    def on_finished(self, code, result):
        self.timer.stop()
        self.last_result = result
        clear_layout(self.result_box)
        state = result.get('status', 'failed')
        if self.operation_kind == 'doctor':
            title = 'Comprobación terminada' if code == 0 else 'Hay comprobaciones por revisar'
            description = 'Consulta el registro para ver el resultado de cada comprobación. El diagnóstico no cambia la configuración.'
        elif self.operation_kind == 'restore':
            title = 'Configuración recuperada' if code == 0 else 'La recuperación necesita atención'
            description = 'Los cambios posteriores se guardan junto al respaldo. Los paquetes del sistema permanecen instalados.'
        else:
            title = {'complete':'Tu espacio está preparado.', 'conflicts':'Tus cambios están protegidos.', 'cancelled':'Instalación detenida.', 'failed':'Hay un paso por resolver.'}.get(state, 'Revisa el resultado.')
            description = {'complete':'La selección se instaló correctamente.',
                'conflicts':'La instalación terminó con archivos personalizados pendientes de revisar. Las propuestas nuevas están en incoming/; esos archivos siguen usando tu versión.',
                'cancelled':'Se detuvo entre operaciones. Puedes repetir la instalación o recuperar los archivos desde el respaldo.',
                'failed':'La instalación no se completó. Consulta el registro, corrige la causa y vuelve a intentarlo; el respaldo permite recuperar los archivos.'}.get(state, '')
        box = surface(self.result_box)
        box.addWidget(label(title, 'heading'))
        box.addWidget(label(description))
        if result.get('message'):
            box.addWidget(label(result['message'], 'error'))
        if result.get('backup'):
            box.addWidget(label('Respaldo: ' + result['backup'], 'small'))
        if result.get('conflicts'):
            conflicts = QPlainTextEdit('\n'.join(result['conflicts']))
            conflicts.setReadOnly(True)
            conflicts.setMaximumHeight(120)
            box.addWidget(conflicts)
        actions = QHBoxLayout()
        actions.addWidget(Button('Ver registro', self.show_log_dialog))
        actions.addWidget(Button('Abrir respaldos', self.show_backups))
        actions.addStretch()
        self.result_box.addLayout(actions)
        if self.operation_kind == 'install' and state == 'complete':
            if self.last_plan and self.last_plan['config_only']:
                self.result_box.addWidget(label('Se copiaron configuraciones. Este modo no instala dependencias ni registra una sesión gráfica.', 'small'))
            elif self.last_plan and 'desktop' in self.last_plan['components']:
                next_box = surface(self.result_box, 'subtle')
                next_box.addWidget(label('Entra a tu nuevo escritorio cuando quieras', 'section'))
                next_box.addWidget(label('Guarda tu trabajo, cierra sesión y elige «Wysun / BSPWM» en la pantalla de acceso.'))
            if self.last_plan and 'boot' in self.last_plan['components']:
                self.result_box.addWidget(label('Blue CRT aparecerá en el próximo inicio. Sus respaldos del sistema están en /var/lib/dotifails/boot/backups.', 'small'))
            if self.last_plan and 'desktop' in self.last_plan['components']:
                self.add_shortcuts(self.result_box)
        else:
            self.result_box.addWidget(Button('Volver a la selección', lambda:self.show_page(2)))
        self.result_box.addWidget(Button('Comprobar instalación', self.run_doctor))
        self.show_page(6)

    def show_log_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Registro de la operación')
        dialog.resize(780, 500)
        layout = QVBoxLayout(dialog)
        log = QPlainTextEdit(self.logs.toPlainText())
        log.setReadOnly(True)
        layout.addWidget(log)
        if self.runner.directory:
            layout.addWidget(label('Registro completo: ' + str(self.runner.directory/'console.log'), 'small'))
        row = QHBoxLayout()
        row.addWidget(Button('Abrir carpeta del registro', lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.runner.directory)))))
        row.addStretch()
        row.addWidget(Button('Cerrar', dialog.accept, 'primary'))
        layout.addLayout(row)
        dialog.exec()

    def run_doctor(self):
        self.start_operation('doctor', '/usr/bin/python3', [str(Path(__file__).with_name('main.py')), 'doctor', '--target-home', str(self.home)])

    def show_backups(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Respaldos y recuperación · Wysun')
        dialog.resize(740, 540)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.addWidget(label('Puedes volver atrás.', 'heading'))
        layout.addWidget(label('Recupera los archivos del hogar de más reciente a más antiguo. Las ediciones posteriores se guardan aparte; los paquetes permanecen instalados.'))
        items = backups(self.home)
        listing = QListWidget()
        listing.setAccessibleName('Respaldos de las configuraciones del hogar')
        status_names = {'complete':'Completado', 'conflicts':'Con cambios personales', 'failed':'Interrumpido', 'cancelled':'Detenido', 'running':'Sin finalizar', 'restored':'Restaurado'}
        for item in items:
            listing.addItem(f"{item['id']}\n{status_names.get(item['status'], item['status'])} · {item['operations']} cambios")
        layout.addWidget(listing, 1)
        if not items:
            layout.addWidget(label('Aún no hay respaldos del hogar. Se crean al instalar.', 'small'))
        from boot_recovery import BootRecoveryDialog
        layout.addWidget(Button('Respaldos del arranque Blue CRT…', lambda:BootRecoveryDialog(self.home, dialog).exec()))
        row = QHBoxLayout()
        inspect = Button('Abrir carpeta', lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(items[listing.currentRow()]['path'])) if listing.currentRow()>=0 else None)
        restore = Button('Restaurar este respaldo', role='primary')
        latest = next((i for i, item in enumerate(items) if item['status'] != 'restored'), None)
        restore.setEnabled(False)
        inspect.setEnabled(bool(items))
        def selection():
            restore.setEnabled(latest is not None and listing.currentRow() == latest)
        listing.currentRowChanged.connect(selection)
        def apply_restore():
            index = listing.currentRow()
            if index != latest or index < 0:
                return
            item = items[index]
            confirm = QMessageBox.question(dialog, 'Restaurar configuración',
                f"Se recuperarán {item['operations']} cambios del respaldo {item['id']}. Las ediciones posteriores se guardarán en changes-before-restore/. ¿Restaurar?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm != QMessageBox.Yes:
                return
            dialog.accept()
            self.start_operation('restore', '/usr/bin/python3', [str(Path(__file__).with_name('main.py')), 'restore', item['id'], '--target-home', str(self.home)])
        restore.clicked.connect(apply_restore)
        row.addWidget(inspect)
        row.addStretch()
        row.addWidget(Button('Cerrar', dialog.reject))
        row.addWidget(restore)
        layout.addLayout(row)
        if latest is not None:
            listing.setCurrentRow(latest)
        dialog.exec()

    def add_shortcuts(self, layout):
        box = surface(layout, 'subtle')
        box.addWidget(label('Cinco atajos para empezar', 'section'))
        for keys, action in (('Super + Espacio','Aplicaciones y búsqueda'), ('Super + Enter','Terminal'), ('Super + N','Conexiones'), ('Super + X','Sesión y energía'), ('Super + Alt + ,','Ajustes del escritorio')):
            row = QHBoxLayout()
            key = label(keys, 'small', False)
            key.setMinimumWidth(170)
            row.addWidget(key)
            row.addWidget(label(action), 1)
            box.addLayout(row)
        box.addWidget(label('Super suele ser la tecla con el logotipo de Windows. Escape cierra los paneles.', 'small'))

    def show_guide(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Primeros pasos · Wysun')
        dialog.resize(590, 480)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.addWidget(label('Hazlo tuyo.', 'heading'))
        layout.addWidget(label('En Ajustes puedes organizar pantallas, personalizar la barra y cambiar el tema. Tus notas y tu historial viven separados de la aplicación.'))
        self.add_shortcuts(layout)
        layout.addWidget(Button('Entendido', dialog.accept, 'primary'))
        dialog.exec()

    def closeEvent(self, event):
        if self.runner.running:
            event.ignore()
            if self.operation_kind == 'restore':
                QMessageBox.information(self, 'Recuperación en curso', 'Espera a que termine la recuperación antes de cerrar.')
            elif not self.runner.cancel_requested:
                answer = QMessageBox.question(self, 'Operación en curso', 'La ventana debe permanecer abierta mientras termina la operación. ¿Solicitar una detención al finalizar la operación actual?', QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
                if answer == QMessageBox.Yes:
                    self.request_stop()
            return
        event.accept()


def launch(source=None, home=None):
    home = Path(home or Path.home())
    previous = load_json(home / '.local/state/dotifails/installed.json', {}).get('source')
    source = Path(source or previous or Path(__file__).resolve().parent.parent)
    app = QApplication.instance() or QApplication(['dotifails-installer'])
    app.setApplicationName('dotifails-installer')
    app.setOrganizationName('Wysun')
    font_path = source/'assets/fonts/Inter/Inter-Variable.ttf'
    if font_path.is_file():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont('Inter', 10))
    app.setStyle('Fusion')
    window = InstallerWindow(source, home)
    screen = app.primaryScreen().availableGeometry()
    window.resize(min(1100, screen.width()-32), min(780, screen.height()-48))
    window.move(screen.center()-window.rect().center())
    window.show()
    return app.exec()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Instalador visual de Wysun')
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    raise SystemExit(launch(args.source))
