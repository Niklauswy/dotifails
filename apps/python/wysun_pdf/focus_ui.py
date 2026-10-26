"""A quiet study session, composed from shared controls and shape tokens."""
import math
from datetime import datetime
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget, QDialog, QHBoxLayout, QLineEdit, QSpinBox, QScrollArea, QVBoxLayout
from wysun_core.qt_theme import color, tokens, extend_style
from wysun_core.ui.style import metric, text_font, paint_symbol, clock
from wysun_core.ui.shapes import cookie
from wysun_core.ui.widgets import IconButton, PillButton, StateLayer
from wysun_core.ui.panels import Panel
from wysun_pdf.study_ui import label, layout, control_height, count


class SessionDial(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.shape = StateLayer(self)
        self.running = False
        self.setFixedHeight(metric('spacing.extraExtraLarge', 5))
        controller.changed.connect(self.refresh)

    def refresh(self):
        running = self.controller.clock.state == 'running'
        if self.running != running:
            self.running = running
            self.shape.to(float(running))
        self.setAccessibleName('Tiempo restante: ' + clock(math.ceil(self.controller.clock.remaining)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - metric('spacing.large', 2)
        box = QRectF((self.width()-side)/2, (self.height()-side)/2, side, side)
        p.setPen(Qt.NoPen)
        p.setBrush(color('fill'))
        p.drawPath(cookie(box, 12, self.shape.amount * 12))
        inset = metric('spacing.small')
        arc = box.adjusted(inset, inset, -inset, -inset)
        p.setPen(QPen(color('accent'), tokens()['border.focus'] * 2, Qt.SolidLine, Qt.RoundCap))
        remaining = self.controller.clock.remaining / self.controller.clock.duration
        p.drawArc(arc, 90 * 16, -round(360 * 16 * remaining))
        p.setFont(text_font('headline.large'))
        p.setPen(color('text'))
        p.drawText(box, Qt.AlignCenter, clock(math.ceil(self.controller.clock.remaining)))


class FocusPanel(Panel):
    closed = Signal()
    reflection_requested = Signal()

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setMinimumWidth(metric('spacing.extraExtraLarge', 6))
        self.setMaximumWidth(metric('spacing.extraExtraLarge', 8))
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        outer = layout(content)
        scroll.setWidget(content)
        shell.addWidget(scroll)
        top = QHBoxLayout()
        top.addWidget(label('Concentración', 'title.large'), 1)
        top.addWidget(IconButton('close', 'Cerrar panel de concentración', self.closed.emit, size=control_height()))
        outer.addLayout(top)
        outer.addWidget(label('UN CAPÍTULO A LA VEZ', 'label.small', 'accent'))
        self.dial = SessionDial(controller)
        outer.addWidget(self.dial)
        self.status = label('Un espacio para leer sin prisa.', 'body.medium')
        outer.addWidget(self.status)
        self.goal = QLineEdit(controller.goal)
        self.goal.setAccessibleName('Objetivo de la sesión, opcional')
        self.goal.setPlaceholderText('¿Qué quieres comprender?')
        self.goal.setMaxLength(500)
        self.goal.setFont(text_font('body.medium'))
        self.goal.setMinimumHeight(control_height())
        extend_style(self.goal, 'QLineEdit {background:@well;color:@text;border:@border.width solid @line;'
                     'border-radius:@rounding.small;padding:@padding.small;}'
                     'QLineEdit:focus {border:@border.focus solid @focus;}')
        outer.addWidget(self.goal)
        durations = QHBoxLayout()
        durations.addWidget(label('Estudio', 'body.small'))
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 180)
        self.minutes.setValue(controller.minutes)
        self.minutes.setSuffix(' min')
        self.minutes.setAccessibleName('Minutos de estudio')
        durations.addWidget(self.minutes)
        durations.addWidget(label('Pausa', 'body.small'))
        self.rest = QSpinBox()
        self.rest.setRange(1, 60)
        self.rest.setValue(controller.break_minutes)
        self.rest.setSuffix(' min')
        self.rest.setAccessibleName('Minutos de descanso')
        durations.addWidget(self.rest)
        outer.addLayout(durations)
        long_row = QHBoxLayout()
        long_row.addWidget(label('Descanso largo · cada 4 bloques', 'body.small'), 1)
        self.long_rest = QSpinBox()
        self.long_rest.setRange(1, 180)
        self.long_rest.setValue(controller.long_break_minutes)
        self.long_rest.setSuffix(' min')
        self.long_rest.setAccessibleName('Minutos de descanso largo')
        long_row.addWidget(self.long_rest)
        outer.addLayout(long_row)
        for spin in (self.minutes, self.rest, self.long_rest):
            # Typed field without the host's arrow buttons, which ignore the theme; arrows/wheel still step.
            spin.setButtonSymbols(QSpinBox.NoButtons)
            spin.setAlignment(Qt.AlignCenter)
            spin.setMinimumHeight(control_height())
            spin.setFont(text_font('body.small'))
            extend_style(spin, 'QSpinBox {background:@well;color:@text;border:@border.width solid @line;'
                         'border-radius:@rounding.small;padding:@padding.small;}'
                         'QSpinBox:focus {border:@border.focus solid @focus;}')
        self.primary = PillButton('play_arrow', 'Empezar', self.toggle, height=control_height())
        outer.addWidget(self.primary)
        self.break_button = PillButton('coffee', 'Tomar un descanso', self.start_break, 'tonal', control_height())
        outer.addWidget(self.break_button)
        self.finish_button = PillButton('stop', 'Terminar sesión', controller.finish, 'tonal', control_height())
        outer.addWidget(self.finish_button)
        self.reflect_button = PillButton('edit_note', 'Anotar lo aprendido', self.reflection_requested.emit,
                                         'tonal', control_height())
        outer.addWidget(self.reflect_button)
        self.history_label = label('', 'body.small', 'muted')
        outer.addWidget(self.history_label)
        outer.addWidget(PillButton('history', 'Historial de sesiones', self.show_history, 'tonal', control_height()))
        outer.addWidget(label('Puedes cerrar este panel y seguir leyendo. El tiempo permanece en la cabecera. '
                              'Al cerrar la última ventana, la sesión queda en pausa.', 'body.small', 'muted'))
        outer.addStretch()
        controller.changed.connect(self.refresh)
        self.refresh()

    def show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Historial de estudio')
        extend_style(dialog, 'QDialog {background:@surface;}')
        outer = layout(dialog)
        outer.addWidget(label('Tiempo para tus ideas', 'headline.small'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        items = layout(content, padding='padding.extraSmall')
        for entry in reversed(self.controller.history):
            try:
                date = datetime.fromtimestamp(entry['ended']).strftime('%d/%m · %H:%M')
                minutes = max(0, int(entry['seconds'])) // 60
            except (KeyError, ValueError, TypeError, OverflowError, OSError):
                continue
            items.addWidget(label(f'{date} · {minutes} min · ' +
                ('Completado' if entry.get('completed') else 'Terminado antes'), 'label.small', 'accent'))
            items.addWidget(label(str(entry.get('goal') or 'Lectura libre'), 'body.medium'))
        if not self.controller.history:
            items.addWidget(label('Tus sesiones aparecerán aquí al completarlas o terminarlas.', 'body.medium'))
        items.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addWidget(PillButton('check', 'Listo', dialog.accept, height=control_height()), 0, Qt.AlignRight)
        dialog.resize(metric('spacing.extraExtraLarge', 11), metric('spacing.extraExtraLarge', 12))
        dialog.exec()

    def toggle(self):
        if self.controller.clock.state in ('idle', 'finished'):
            self.controller.minutes, self.controller.break_minutes = self.minutes.value(), self.rest.value()
            self.controller.long_break_minutes = self.long_rest.value()
            self.controller.start(self.minutes.value(), self.goal.text())
        else:
            self.controller.toggle()

    def start_break(self):
        self.controller.start(self.controller.next_break, self.goal.text(), 'break')

    def refresh(self):
        state = self.controller.clock.state
        phase = self.controller.clock.phase
        names = {'idle': ('play_arrow', 'Empezar'), 'running': ('pause', 'Pausar'),
                 'paused': ('play_arrow', 'Reanudar'), 'finished': ('play_arrow', 'Nuevo bloque')}
        self.primary.set_content(*names[state])
        text = {'idle': 'Un espacio para leer sin prisa.', 'running': 'Tiempo de descanso.' if phase == 'break' else 'Tu lectura tiene este momento.',
                'paused': 'En pausa. Retoma cuando quieras.', 'finished': 'Bloque completado. ¿Qué idea te llevas?'}
        self.status.setText(text[state])
        self.break_button.set_content('coffee', f'Descansar {self.controller.next_break} min')
        history = self.controller.history
        self.history_label.setText(count(self.controller.completed_blocks, 'bloque completado', 'bloques completados') +
            f' · {sum(h.get("seconds", 0) for h in history) // 60} min de estudio registrados' +
            ('\nÚltimo objetivo: ' + (str(history[-1].get('goal') or '') or 'lectura libre') if history else ''))
        self.finish_button.setVisible(state != 'idle')
        self.break_button.setVisible(state == 'finished' and phase == 'study')
        self.reflect_button.setVisible(state in ('paused', 'finished'))
        if state in ('running', 'paused'):
            self.goal.setText(self.controller.goal)
        for widget in (self.goal, self.minutes, self.rest, self.long_rest):
            widget.setEnabled(state in ('idle', 'finished'))
        self.dial.refresh()
