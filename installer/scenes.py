"""Expressive centrepieces of Wysun Installer: one living composition per screen.

Shapes are the shell's M3 vocabulary (cookies, circles, squircles); every colour, size and duration
comes from the theme tokens and every loop stops while hidden or under reduced motion.
"""
import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from material_widgets import (SOLID, StateLayer, animate, blob, color, cookie, focus_ring, metric, paint_symbol,
                              squircle, text_font, tokens)
from ui_motion import reduced_motion


class Ticker:
    """A shared frame clock for one widget: runs only while visible and motion is allowed."""

    def init_ticker(self, interval=33):
        self.clock = 0.0
        self._ticker = QTimer(self, interval=interval)
        self._ticker.timeout.connect(self._advance)

    def _advance(self):
        self.clock += self._ticker.interval() / 1000
        self.tick()
        self.update()

    def tick(self):
        pass

    def sync_ticker(self, wanted=True):
        if wanted and self.isVisible() and not reduced_motion(self.window()):
            self._ticker.start()
        else:
            self._ticker.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_ticker(self.animating())

    def hideEvent(self, event):
        self._ticker.stop()
        super().hideEvent(event)

    def animating(self):
        return True


def mix(a, b, amount):
    result = QColor(a)
    result.setRedF(a.redF() + (b.redF() - a.redF()) * amount)
    result.setGreenF(a.greenF() + (b.greenF() - a.greenF()) * amount)
    result.setBlueF(a.blueF() + (b.blueF() - a.blueF()) * amount)
    result.setAlphaF(a.alphaF() + (b.alphaF() - a.alphaF()) * amount)
    return result


# --------------------------------------------------------------------------- stepper
class Stepper(Ticker, QWidget):
    """The journey as shapes on a thread: the current step is a turning cookie with its name,
    finished ones settle into checked circles, the rest wait as small dots."""

    selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ticker()
        self.steps = []
        self.current = 0
        self.position = 0.0
        self.reachable = set()
        self.hovered = -1
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedHeight(metric('space_xl') * 3)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName('Pasos de la instalación')

    def set_steps(self, steps):
        self.steps = list(steps)
        self.update()

    def set_current(self, index, reachable=None, animate_change=True):
        if reachable is not None:
            self.reachable = set(reachable)
        start = self.position
        self.current = index
        self.setAccessibleDescription(self.steps[index][1] if self.steps else '')
        if animate_change and self.isVisible():
            animate(self, tokens()['motion_enter'] * 2, self._move, start, float(index), QEasingCurve.OutBack)
        else:
            self._move(float(index))

    def _move(self, value):
        self.position = value
        self.update()

    def centres(self):
        count = max(1, len(self.steps))
        spacing = min(self.width() / count, metric('space_xl') * 6)
        left = (self.width() - spacing * (count - 1)) / 2
        top = metric('space_xl') * .75 + metric('space_m')
        return [QPointF(left + spacing * i, top) for i in range(count)]

    def _hit(self, point):
        for index, centre in enumerate(self.centres()):
            if abs(point.x() - centre.x()) < metric('space_xl') * 1.6 and point.y() < self.height():
                return index
        return -1

    def mouseMoveEvent(self, event):
        hovered = self._hit(event.position())
        if hovered != self.hovered:
            self.hovered = hovered
            self.setCursor(Qt.PointingHandCursor if hovered in self.reachable else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        self.hovered = -1
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        index = self._hit(event.position())
        if index in self.reachable and index != self.current:
            self.selected.emit(index)

    def keyPressEvent(self, event):
        step = {Qt.Key_Left: -1, Qt.Key_Right: 1}.get(event.key())
        target = self.current + step if step else None
        if target is not None and target in self.reachable:
            self.selected.emit(target)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        if not self.steps:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        centres = self.centres()
        big, small = metric('space_xl') * 1.5, metric('space_l')
        # Thread: the travelled part is accent.
        for index in range(len(centres) - 1):
            a, b = centres[index], centres[index + 1]
            done = min(1.0, max(0.0, self.position - index))
            painter.setPen(QPen(color('line'), 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(a, b)
            if done:
                painter.setPen(QPen(color('accent'), 2, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(a, QPointF(a.x() + (b.x() - a.x()) * done, a.y()))
        for index, (centre, (symbol, title)) in enumerate(zip(centres, self.steps)):
            near = max(0.0, 1 - abs(self.position - index))
            side = small + (big - small) * near
            box = QRectF(centre.x() - side / 2, centre.y() - side / 2, side, side)
            painter.setPen(Qt.NoPen)
            if near > .05:
                painter.setBrush(color('accent', round(40 * near)))
                painter.drawPath(blob(box.adjusted(-8, -8, 8, 8), 9, .08, -self.clock * 20))
                painter.setBrush(color('accent'))
                painter.drawPath(blob(box, 12, .07 * near, self.clock * 30))
                paint_symbol(painter, box, symbol, 'on_accent', side * .5, filled=symbol in SOLID)
            elif index < self.position:
                painter.setBrush(color('accent'))
                painter.drawEllipse(box)
                paint_symbol(painter, box, 'check', 'on_accent', side * .7, filled=True)
            else:
                reachable = index in self.reachable
                painter.setBrush(color('fill' if reachable else 'well'))
                painter.drawEllipse(box)
                paint_symbol(painter, box, symbol, 'glyph' if reachable else 'disabled', side * .62)
            if index == self.hovered and index != self.current and index in self.reachable:
                painter.setBrush(color('tint', 22))
                painter.drawEllipse(box.adjusted(-4, -4, 4, 4))
            font = text_font('small', 650 if near > .5 else 500)
            painter.setFont(font)
            painter.setPen(mix(color('muted'), color('text_strong'), near))
            label = QRectF(centre.x() - metric('space_xl') * 3, centre.y() + big / 2 + 2, metric('space_xl') * 6, metric('space_l') + 2)
            if near > .3 or self.width() > len(self.steps) * metric('space_xl') * 5:
                painter.drawText(label, Qt.AlignHCenter | Qt.AlignTop, title)
        if self.hasFocus() and self.window().isActiveWindow():
            centre = centres[self.current]
            painter.setPen(QPen(color('focus'), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(centre, big / 2 + 10, big / 2 + 10)


# --------------------------------------------------------------------------- scan
class ScanScene(Ticker, QWidget):
    """«Tu equipo»: the system's badge with pulses while it is read, then its facts pop in around it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ticker()
        self.initial, self.name, self.detail = '?', '', ''
        self.state = 'scanning'
        self.facts = []          # [(level, text, amount)]
        self.settle = 1.0
        self.setFixedHeight(metric('space_xl') * 17)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_system(self, initial, name, detail):
        self.initial, self.name, self.detail = initial, name, detail
        self.setAccessibleName(name)
        self.setAccessibleDescription(detail)
        self.update()

    def scanning(self):
        self.state, self.facts = 'scanning', []
        self.sync_ticker(True)
        self.update()

    def set_facts(self, facts, state):
        """``facts``: [(level, text)] in order; ``state`` ok | warning | error."""
        self.state = state
        self.facts = [[level, text, 0.0] for level, text in facts]
        for index, fact in enumerate(self.facts):
            def grow(value, fact=fact):
                fact[2] = value
                self.update()
            animate(self, tokens()['motion_enter'] + 120, grow, 0.0, 1.0, QEasingCurve.OutBack, delay=120 + index * 90)
        self.settle = 0.0
        animate(self, tokens()['motion_enter'] * 2, self._settle, 0.0, 1.0, QEasingCurve.OutBack)
        self.setAccessibleDescription(self.detail + '. ' + '. '.join(text for _level, text in facts))
        self.update()

    def _settle(self, value):
        self.settle = value
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        side = min(rect.height() * .34, metric('space_xl') * 6.5)
        centre = QPointF(rect.center().x(), metric('space_xl') + side * .9)
        badge = QRectF(centre.x() - side / 2, centre.y() - side / 2, side, side)
        painter.setPen(Qt.NoPen)
        if self.state == 'scanning':
            for ring in range(3):
                phase = (self.clock * .55 + ring / 3) % 1.0
                radius = side / 2 * (1 + phase * 1.1)
                painter.setPen(QPen(color('accent', round(150 * (1 - phase))), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(centre, radius, radius)
            painter.setPen(Qt.NoPen)
            for moon in range(5):
                angle = self.clock * (1.4 + moon * .17) + moon * 1.26
                radius = side * (.72 + .08 * math.sin(self.clock * 2 + moon))
                point = QPointF(centre.x() + math.cos(angle) * radius, centre.y() + math.sin(angle) * radius * .82)
                size = side * (.07 + .02 * (moon % 2))
                painter.setBrush(color('accent', 200 - moon * 25))
                painter.drawPath(cookie(QRectF(point.x() - size, point.y() - size, size * 2, size * 2), (4, 6, 9)[moon % 3],
                                        self.clock * 90))
        else:
            tone = {'ok': 'accent', 'warning': 'warning', 'error': 'danger'}[self.state]
            halo = side * (.62 + .1 * self.settle)
            painter.setBrush(color(tone, 34))
            painter.drawPath(blob(QRectF(centre.x() - halo, centre.y() - halo, halo * 2, halo * 2), 9, .06, -self.clock * 8))
        painter.setBrush(color('shadow'))
        painter.drawPath(cookie(badge.translated(0, side * .04), 9, self.clock * 12))
        painter.setBrush(color('danger' if self.state == 'error' else 'accent'))
        painter.drawPath(cookie(badge, 9, self.clock * 12))
        painter.setFont(text_font('title', 800, side / max(1, metric('font_title')) * .4))
        painter.setPen(color('on_accent'))
        painter.drawText(badge, Qt.AlignCenter, self.initial)
        if self.state != 'scanning' and self.settle > .01:
            mark = side * .32 * min(1.1, self.settle)
            spot = QRectF(badge.right() - mark * .9, badge.bottom() - mark * .9, mark, mark)
            painter.setBrush(color('surface'))
            painter.drawEllipse(spot.adjusted(-3, -3, 3, 3))
            painter.setBrush(color({'ok': 'accent', 'warning': 'warning', 'error': 'danger'}[self.state]))
            painter.drawEllipse(spot)
            paint_symbol(painter, spot, {'ok': 'check', 'warning': 'priority_high', 'error': 'close'}[self.state],
                         'on_accent', mark * .7, filled=True)
        y = badge.bottom() + metric('space_xl')
        painter.setFont(text_font('title', 750, 1.25))
        painter.setPen(color('text_strong'))
        metrics = painter.fontMetrics()
        painter.drawText(QRectF(0, y, rect.width(), metrics.height()), Qt.AlignHCenter | Qt.AlignVCenter,
                         metrics.elidedText(self.name, Qt.ElideRight, int(rect.width() - 40)))
        y += metrics.height() + metric('space_xs')
        painter.setFont(text_font('body'))
        painter.setPen(color('muted'))
        line = painter.fontMetrics().height()
        painter.drawText(QRectF(0, y, rect.width(), line), Qt.AlignHCenter | Qt.AlignVCenter,
                         'Leyendo tu equipo…' if self.state == 'scanning' else self.detail)
        y += line + metric('space_l')
        self._paint_facts(painter, rect, y)

    def _paint_facts(self, painter, rect, top):
        font = text_font('small', 600)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        height = metric('space_xl') + metric('space_xs')
        gap = metric('space_s')
        pills = []
        for level, text, amount in self.facts:
            width = metrics.horizontalAdvance(text) + height + metric('space_m') * 2
            pills.append((level, text, amount, width))
        rows, row, used = [], [], 0
        limit = rect.width() - metric('space_xl') * 2
        for pill in pills:
            if row and used + pill[3] > limit:
                rows.append((row, used - gap))
                row, used = [], 0
            row.append(pill)
            used += pill[3] + gap
        if row:
            rows.append((row, used - gap))
        y = top
        for row, width in rows:
            x = (rect.width() - width) / 2
            for level, text, amount, pill_width in row:
                box = QRectF(x, y, pill_width, height)
                painter.save()
                painter.translate(box.center())
                painter.scale(max(.01, amount), max(.01, amount))
                painter.translate(-box.center())
                painter.setOpacity(min(1.0, amount))
                tone = {'error': 'danger_soft', 'warning': 'warning_soft'}.get(level, 'well')
                painter.setPen(Qt.NoPen)
                painter.setBrush(color(tone))
                painter.drawRoundedRect(box, height / 2, height / 2)
                dot = QRectF(box.left() + 5, box.top() + 5, height - 10, height - 10)
                painter.setBrush(color({'error': 'danger', 'warning': 'warning', 'info': 'fill'}.get(level, 'accent')))
                painter.drawEllipse(dot)
                symbol = {'error': 'close', 'warning': 'priority_high', 'info': 'info'}.get(level, 'check')
                paint_symbol(painter, dot, symbol, 'glyph' if level == 'info' else 'on_accent', dot.height() * .7,
                             filled=symbol in SOLID)
                painter.setPen(color('text'))
                painter.drawText(QRectF(dot.right() + metric('space_s'), box.top(), pill_width, height),
                                 Qt.AlignLeft | Qt.AlignVCenter, text)
                painter.restore()
                x += pill_width + gap
            y += height + gap


# --------------------------------------------------------------------------- content
class CoreCard(Ticker, QWidget):
    """What every installation brings, as one accent piece with its parts floating as chips."""

    PARTS = ('Hyprland', 'Shell', 'Lanzador', 'Settings', 'Music', 'Files', 'Recorder', 'Capturas con OCR',
             'Bloqueo', 'Fondos animados', 'Terminal Ghostty', 'Zsh')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ticker(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(metric('space_xl') * 7 + metric('space_s'))
        self.setAccessibleName('Wysun, siempre incluido')
        self.setAccessibleDescription(', '.join(self.PARTS))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = tokens()['radius_l']
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        painter.fillRect(rect, color('accent'))
        side = rect.height() * 1.25
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('on_accent', 26))
        painter.drawPath(cookie(QRectF(rect.right() - side * .62, rect.center().y() - side / 2, side, side), 12, self.clock * 6))
        painter.setBrush(color('on_accent', 38))
        small = side * .5
        painter.drawPath(cookie(QRectF(rect.right() - side * .42, rect.center().y() - small / 2, small, small), 9, -self.clock * 10))
        painter.setFont(text_font('title', 800, small / max(1, metric('font_title')) * .38))
        painter.setPen(color('on_accent'))
        painter.drawText(QRectF(rect.right() - side * .42, rect.center().y() - small / 2, small, small), Qt.AlignCenter, 'W')
        pad = metric('space_xl')
        font = text_font('caption', 700)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
        painter.setFont(font)
        painter.drawText(QRectF(pad, pad, rect.width(), 16), Qt.AlignLeft | Qt.AlignVCenter, 'SIEMPRE INCLUIDO')
        painter.setFont(text_font('title', 800, 1.35))
        painter.drawText(QRectF(pad, pad + 20, rect.width(), metric('font_title') * 2), Qt.AlignLeft | Qt.AlignVCenter, 'Wysun')
        font = text_font('small', 600)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        height = metric('space_xl')
        x, y = float(pad), pad + 20 + metric('font_title') * 2 + metric('space_s')
        limit = rect.width() - side * .55
        for index, part in enumerate(self.PARTS):
            width = metrics.horizontalAdvance(part) + metric('space_l') * 2
            if x + width > limit:
                x, y = float(pad), y + height + metric('space_s')
            if y + height > rect.height() - metric('space_s'):
                break
            bob = math.sin(self.clock * 1.6 + index * .9) * 1.5
            chip = QRectF(x, y + bob, width, height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('on_accent', 34))
            painter.drawRoundedRect(chip, height / 2, height / 2)
            painter.setPen(color('on_accent'))
            painter.drawText(chip, Qt.AlignCenter, part)
            x += width + metric('space_s')


class AddonTile(QAbstractButton):
    """An optional piece: a ghost outline until chosen, then it fills and turns."""

    def __init__(self, symbol, title, detail, sides=9, parent=None):
        super().__init__(parent)
        self.symbol, self.title, self.detail, self.sides = symbol, title, detail, sides
        self.layer = StateLayer(self)
        self.pick = StateLayer(self)
        self.pop = 1.0
        self.angle = 0.0
        self._spin = QTimer(self, interval=40)
        self._spin.timeout.connect(self._turn)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setAccessibleDescription(detail)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(metric('space_xl') * 8)
        self.toggled.connect(self._toggled)

    def _toggled(self, on):
        self.pick.to(1.0 if on else 0.0)
        animate(self, tokens()['motion_enter'] + 140, self._pop, .82, 1.0, QEasingCurve.OutBack)
        self._sync()

    def _pop(self, value):
        self.pop = value
        self.update()

    def _sync(self):
        if self.isChecked() and self.isVisible() and not reduced_motion(self.window()):
            self._spin.start()
        else:
            self._spin.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync()

    def hideEvent(self, event):
        self._spin.stop()
        super().hideEvent(event)

    def _turn(self):
        self.angle = (self.angle + .8) % 360
        self.update()

    def sizeHint(self):
        return QSize(metric('space_xl') * 8, self.height())

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = tokens()['radius_l']
        on = self.pick.amount
        painter.setPen(Qt.NoPen)
        painter.setBrush(mix(color('well'), color('nav_selected'), on))
        painter.drawRoundedRect(rect, radius, radius)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('tint', round(12 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_l')
        side = min(rect.height() * .5, rect.width() * .5) * self.pop
        centre = QPointF(rect.center().x(), pad + rect.height() * .28)
        box = QRectF(centre.x() - side / 2, centre.y() - side / 2, side, side)
        shape = cookie(box, self.sides, self.angle + 25 * self.layer.amount)
        if on > .01:
            painter.setBrush(mix(color('fill'), color('accent'), on))
            painter.drawPath(shape)
        if on < .99:
            pen = QPen(color('line_strong', round(255 * (1 - on))), 2, Qt.DashLine, Qt.RoundCap)
            pen.setDashPattern([3, 4])
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(shape)
            painter.setPen(Qt.NoPen)
        paint_symbol(painter, box, self.symbol, mix(color('glyph_muted'), color('on_accent'), on), side * .42)
        badge = QRectF(rect.right() - pad - metric('space_xl'), pad, metric('space_xl'), metric('space_xl'))
        painter.setBrush(mix(color('fill'), color('accent'), on))
        painter.drawEllipse(badge)
        paint_symbol(painter, badge, 'check' if self.isChecked() else 'add', 'on_accent' if self.isChecked() else 'glyph',
                     badge.height() * .7, filled=True)
        y = box.bottom() + metric('space_l')
        painter.setFont(text_font('heading', 700))
        painter.setPen(color('text_strong'))
        title = painter.fontMetrics().height()
        painter.drawText(QRectF(pad, y, rect.width() - pad * 2, title), Qt.AlignHCenter | Qt.AlignVCenter, self.title)
        painter.setFont(text_font('small'))
        painter.setPen(color('muted'))
        painter.drawText(QRectF(pad, y + title + 2, rect.width() - pad * 2, rect.bottom() - y - title - pad),
                         Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.detail)
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)


class AppBubble(QAbstractButton):
    """An optional application: a round bubble that fills and pops when added."""

    def __init__(self, symbol, title, detail, parent=None):
        super().__init__(parent)
        self.symbol, self.title, self.detail = symbol, title, detail
        self.layer = StateLayer(self)
        self.pick = StateLayer(self)
        self.pop = 1.0
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setAccessibleDescription(detail)
        self.setToolTip(f'{title} · {detail} · Flatpak')
        self.setFixedSize(metric('space_xl') * 5, metric('space_xl') * 5)
        self.toggled.connect(self._toggled)

    def _toggled(self, on):
        self.pick.to(1.0 if on else 0.0)
        animate(self, tokens()['motion_enter'] + 140, self._pop, .7, 1.0, QEasingCurve.OutBack)

    def _pop(self, value):
        self.pop = value
        self.update()

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        on = self.pick.amount
        side = rect.width() * .62 * self.pop
        box = QRectF(rect.center().x() - side / 2, metric('space_xs') + (rect.width() * .62 - side) / 2, side, side)
        painter.setPen(Qt.NoPen)
        painter.setBrush(mix(color('well'), color('accent'), on))
        painter.drawPath(blob(box, 9, .07 * on, 30 * on))
        if self.layer.amount:
            painter.setBrush(color('tint', round(16 * self.layer.amount)))
            painter.drawEllipse(box)
        paint_symbol(painter, box, self.symbol, mix(color('glyph'), color('on_accent'), on), side * .44)
        if on > .02:
            mark = side * .34 * on
            spot = QRectF(box.right() - mark * .8, box.top() - mark * .1, mark, mark)
            painter.setBrush(color('surface'))
            painter.drawEllipse(spot.adjusted(-2, -2, 2, 2))
            painter.setBrush(color('accent'))
            painter.drawEllipse(spot)
            paint_symbol(painter, spot, 'check', 'on_accent', mark * .72, filled=True)
        painter.setFont(text_font('body', 600))
        painter.setPen(color('text_strong'))
        painter.drawText(QRectF(0, rect.width() * .66, rect.width(), metric('space_l') + 4), Qt.AlignHCenter | Qt.AlignVCenter, self.title)
        painter.setFont(text_font('caption'))
        painter.setPen(color('muted'))
        painter.drawText(QRectF(0, rect.width() * .66 + metric('space_l') + 4, rect.width(), metric('space_l')),
                         Qt.AlignHCenter | Qt.AlignVCenter, self.detail)
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, box.adjusted(-4, -4, 4, 4), side / 2 + 4)


# --------------------------------------------------------------------------- run
class RunScene(Ticker, QWidget):
    """Installation as one living shape: each stage gives it new lobes and its own symbol; dots below
    count the stages. It settles into a checked circle and bursts when everything is done."""

    LOBES = (12, 9, 7, 6, 4, 9, 12, 7)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ticker()
        self.state = 'idle'      # idle | active | done | warning | error | cancelled
        self.symbol = 'download'
        self.index, self.total = 0, 0
        self.lobes = 12
        self.breath = 1.0
        self.settle = 1.0
        self.burst = 0.0
        self.dots = 0.0
        self.setMinimumHeight(metric('space_xl') * 12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(metric('space_xl') * 13)

    def start(self, total, symbol='download'):
        self.state, self.symbol, self.index, self.total = 'active', symbol, 0, total
        self.dots, self.settle, self.burst = 0.0, 1.0, 0.0
        self.sync_ticker(True)
        self.update()

    def stage(self, index, total, symbol):
        self.total = max(total, 1)
        swapped = {'done': False}

        def breathe(value):
            # Shrink, swap lobes at the narrowest moment, grow back: the shape seems to morph.
            self.breath = 1 - .22 * math.sin(value * math.pi)
            if value >= .5 and not swapped['done']:
                swapped['done'] = True
                self.lobes = self.LOBES[index % len(self.LOBES)]
                self.symbol = symbol
            self.update()
        if self.isVisible() and not reduced_motion(self.window()):
            animate(self, tokens()['motion_enter'] * 2, breathe, 0.0, 1.0, QEasingCurve.InOutCubic)
        else:
            self.lobes, self.symbol = self.LOBES[index % len(self.LOBES)], symbol
        animate(self, tokens()['motion_enter'] * 2, self._dots, self.dots, float(index), QEasingCurve.OutCubic)
        self.index = index

    def advance_dots(self, done):
        animate(self, tokens()['motion_enter'], self._dots, self.dots, float(done), QEasingCurve.OutCubic)

    def _dots(self, value):
        self.dots = value
        self.update()

    def finish(self, state):
        self.state = state
        self.settle = 0.0
        animate(self, tokens()['motion_enter'] * 3, self._settle, 0.0, 1.0, QEasingCurve.OutBack)
        if state == 'done':
            self.dots = float(self.total)
            animate(self, 1300, self._burst, 0.0, 1.0, QEasingCurve.OutCubic)
        self.update()

    def _settle(self, value):
        self.settle = value
        self.update()

    def _burst(self, value):
        self.burst = value
        self.update()

    def animating(self):
        return self.state != 'idle'

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        dots_height = metric('space_xl') * 1.5
        side = min((rect.height() - dots_height) / 1.6, rect.width() * .35)
        centre = QPointF(rect.center().x(), (rect.height() - dots_height) / 2 + metric('space_s'))
        painter.setPen(Qt.NoPen)
        active = self.state == 'active'
        tone = {'error': 'danger', 'warning': 'warning', 'cancelled': 'fill'}.get(self.state, 'accent')
        # Halo: two soft shapes counter-rotating behind.
        for ring, (lobes, alpha, grow, speed) in enumerate(((9, 30, .26, -14), (6, 20, .44, 9))):
            pulse = (.04 * math.sin(self.clock * 2.2 + ring)) if active else 0.0
            size = side * (1 + grow + pulse)
            painter.setBrush(color(tone, alpha))
            painter.drawPath(blob(QRectF(centre.x() - size / 2, centre.y() - size / 2, size, size), lobes, .08,
                                  self.clock * speed))
        if 0 < self.burst < 1:
            for index in range(14):
                angle = index / 14 * 2 * math.pi + .2
                distance = side * (.5 + 1.1 * self.burst) * (1 + .15 * (index % 3))
                size = side * .12 * (1 - self.burst * .5)
                point = QPointF(centre.x() + math.cos(angle) * distance, centre.y() + math.sin(angle) * distance * .8)
                painter.setBrush(color('accent' if index % 2 else 'accent_muted', round(230 * (1 - self.burst))))
                painter.drawPath(cookie(QRectF(point.x() - size / 2, point.y() - size / 2, size, size),
                                        (4, 6, 9, 12)[index % 4], self.burst * 200 + index * 30))
        if active or self.state == 'idle':
            size = side * self.breath
            box = QRectF(centre.x() - size / 2, centre.y() - size / 2, size, size)
            painter.setBrush(color('shadow'))
            painter.drawPath(blob(box.translated(0, size * .04), self.lobes, .07, self.clock * 24))
            painter.setBrush(color('accent'))
            painter.drawPath(blob(box, self.lobes, .06 + .025 * math.sin(self.clock * 3), self.clock * 24))
            paint_symbol(painter, box, self.symbol, 'on_accent', size * .36, filled=self.symbol in SOLID)
        else:
            settle = self.settle
            size = side * (.84 + .16 * min(1.1, settle))
            box = QRectF(centre.x() - size / 2, centre.y() - size / 2, size, size)
            painter.setBrush(color(tone))
            if self.state == 'error':
                painter.drawPath(cookie(box, 4, 45 + 20 * (1 - settle)))
            elif self.state == 'warning':
                painter.drawPath(squircle(box, .25))
            else:
                painter.drawPath(blob(box, self.lobes, .07 * max(0.0, 1 - settle), 0))
            glyph = {'done': 'check', 'error': 'close', 'warning': 'priority_high', 'cancelled': 'pause'}[self.state]
            painter.setOpacity(max(0.0, min(1.0, settle)))
            paint_symbol(painter, box, glyph, 'glyph' if self.state == 'cancelled' else 'on_accent',
                         size * .45 * max(.3, min(1.1, settle)), filled=True)
            painter.setOpacity(1)
        if self.total:
            y = rect.height() - dots_height / 2
            dot, pill, gap = metric('space_s'), metric('space_xl'), metric('space_s')
            width = (self.total - 1) * (dot + gap) + pill
            x = rect.center().x() - width / 2
            for index in range(self.total):
                near = max(0.0, 1 - abs(self.dots - index)) if active else 0.0
                length = dot + (pill - dot) * near
                done = index < self.dots - .5 or self.state == 'done'
                painter.setBrush(color('accent') if done or near > .5 else color('line_strong'))
                painter.drawRoundedRect(QRectF(x, y - dot / 2, length, dot), dot / 2, dot / 2)
                x += length + gap


class PillSwitch(QAbstractButton):
    """One quiet choice: a pill holding a switch and its sentence."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        from material_widgets import paint_switch
        self._paint_switch = paint_switch
        self.setText(text)
        self.layer = StateLayer(self)
        self.knob = StateLayer(self)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(text)
        self.setFont(text_font('body', 600))
        self.setFixedHeight(metric('space_xl') * 2 + metric('space_xs'))
        self.toggled.connect(lambda on: self.knob.to(1.0 if on else 0.0))

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + metric('space_xl') * 4 + metric('space_l'), self.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def setChecked(self, value):
        super().setChecked(value)
        self.knob.to(1.0 if value else 0.0)

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('well'))
        painter.drawRoundedRect(rect, radius, radius)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('tint', round(14 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_s')
        track = QRectF(pad + 2, (rect.height() - metric('space_xl') - metric('space_s')) / 2,
                       metric('space_xl') * 2 + metric('space_xs'), metric('space_xl') + metric('space_s'))
        self._paint_switch(painter, track, self.knob.amount, self.isEnabled())
        painter.setFont(self.font())
        painter.setPen(color('text_strong' if self.isEnabled() else 'disabled'))
        painter.drawText(QRectF(track.right() + metric('space_m'), 0, rect.width() - track.right() - metric('space_l'), rect.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, self.text())
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)
