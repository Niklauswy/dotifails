"""The «Apagado automático» editor: a modal of rule rows that the app shows over the mosaic.

It is a plain object: :meth:`Editor.key` takes key events and answers ``'save'``,
``'cancel'`` or ``None``, :meth:`Editor.draw` paints the panel, and :meth:`Editor.result`
gives the rules, the one-off power-off and the target VMs to apply. The app owns the
animation, the SSH calls and the toasts.

Rows (``↑↓`` moves between them; rows of a rule that is off stay hidden):

* **Horario fijo** — ``espacio`` on/off, ``←→`` ±15 min, ``RePág/AvPág`` ±1 h;
  **Días** — ``←→`` todos / lunes a viernes / fines de semana, ``1``–``7`` one day.
* **Tiempo máximo encendida** — hours after it starts.
* **Sin actividad** — minutes without use; then **CPU por debajo de** and
  **SSH abierta cuenta como uso**.
* **Una vez** — a one-off power-off N minutes from now (an existing one is shown as is).
* **Aplicar a** — this VM, every running VM, or a list to tick (``espacio``).
"""
from __future__ import annotations

import time

from wysun_core.tui.anim import Rect
from wysun_core.tui.canvas import Style
from wysun_core.tui.draw import box, truncate
from wysun_core.tui import kit

from .. import autostop
from ..autostop import Once, Rules

__all__ = ['Editor', 'HINTS']

HINTS = [('↑↓', 'mover'), ('espacio', 'activar'), ('←→', 'cambiar'), ('⏎', 'guardar'),
         ('Esc', 'cancelar')]
LABEL_WIDTH = 24
SHORT_REASON = {'schedule': 'horario fijo', 'max': 'tiempo máximo', 'once': 'una vez'}
TARGETS = ('one', 'running', 'pick')


class Editor:
    """State of the editor for the VM ``alias`` among ``views`` (the mosaic's VmViews)."""

    def __init__(self, views, alias, status=None, now=None):
        self.views = list(views)
        self.alias = alias
        self.row = 0
        self.target = 'one'
        self.picked = {alias}
        self.touched = False
        self.once_touched = False
        self.loaded = None
        self.load(status, now)

    # -- data -------------------------------------------------------------
    def load(self, status, now=None):
        """Fill the rows from what the VM reported (``None``: still reading, defaults)."""
        now = time.time() if now is None else now
        self.status = status
        rules = status.rules if status is not None else Rules()
        self.loaded = rules if status is not None and status.installed else Rules()
        self.schedule_on = bool(rules.schedule_at)
        self.at = rules.schedule_at or '02:00'
        self.days = rules.days or '1234567'
        self.max_on = rules.max_hours > 0
        self.max_hours = rules.max_hours or 8
        self.idle_on = rules.idle_minutes > 0
        self.idle_minutes = rules.idle_minutes or 30
        self.idle_cpu = rules.idle_cpu or 10
        self.idle_ssh = rules.idle_ssh
        self.idle_procs = rules.idle_procs
        self.once_at = status.once_at if status is not None and status.once_at > now else 0
        self.once_on = self.once_at > 0
        self.once_minutes = 60
        self.once_touched = False

    @property
    def reading(self) -> bool:
        return self.status is None

    def view(self, alias=None):
        alias = alias or self.alias
        return next((view for view in self.views if view.inst.alias == alias), None)

    def running(self):
        return [view for view in self.views if view.inst.running]

    def targets(self) -> list[str]:
        if self.target == 'running':
            return [view.inst.alias for view in self.running()]
        if self.target == 'pick':
            return [view.inst.alias for view in self.running() if view.inst.alias in self.picked]
        return [self.alias]

    def rules(self, tz=None) -> Rules:
        return Rules(
            schedule_at=self.at if self.schedule_on and self.days else None,
            days=self.days or '1234567',
            tz=tz or autostop.local_tz(),                # «02:00» means 02:00 on this computer
            max_hours=self.max_hours if self.max_on else 0,
            idle_minutes=self.idle_minutes if self.idle_on else 0,
            idle_cpu=self.idle_cpu,
            idle_ssh=self.idle_ssh,
            idle_procs=tuple(self.idle_procs),
        )

    def once(self) -> Once:
        if not self.once_touched:
            return Once('keep')
        if not self.once_on:
            return Once('cancel')
        return Once('set', self.once_minutes)

    # -- rows -------------------------------------------------------------
    def rows(self) -> list[str]:
        rows = ['schedule']
        if self.schedule_on:
            rows.append('days')
        rows.append('max')
        rows.append('idle')
        if self.idle_on:
            rows += ['idle_cpu', 'idle_ssh']
        rows += ['once', 'target']
        if self.target == 'pick':
            rows += [f'vm:{view.inst.alias}' for view in self.running()]
        return rows

    def current(self) -> str:
        rows = self.rows()
        self.row = max(0, min(len(rows) - 1, self.row))
        return rows[self.row]

    def key(self, event):
        """Handle one key; returns ``'save'``, ``'cancel'`` or ``None``."""
        name = event.name
        if name == 'escape':
            return 'cancel'
        if name == 'enter':
            return 'save' if self.targets() else None
        if name in ('up', 'backtab'):
            self.row = max(0, self.row - 1)
            return None
        if name in ('down', 'tab'):
            self.row = min(len(self.rows()) - 1, self.row + 1)
            return None
        row = self.current()
        if name in ('left', 'right'):
            self._adjust(row, -1 if name == 'left' else 1, small=True)
        elif name in ('pageup', 'pagedown'):
            self._adjust(row, 1 if name == 'pageup' else -1, small=False)
        elif name == 'char' and event.char == ' ':
            self._toggle(row)
        elif name == 'char' and row == 'days' and event.char in '1234567':
            digits = set(self.days) ^ {event.char}
            if digits:                                   # never all days off
                self.days = ''.join(sorted(digits))
                self.touched = True
        return None

    def _toggle(self, row):
        self.touched = True
        if row == 'schedule':
            self.schedule_on = not self.schedule_on
        elif row == 'max':
            self.max_on = not self.max_on
        elif row == 'idle':
            self.idle_on = not self.idle_on
        elif row == 'idle_ssh':
            self.idle_ssh = not self.idle_ssh
        elif row == 'once':
            self.once_on = not self.once_on
            self.once_touched = True
            if self.once_on:
                self.once_at = 0
        elif row == 'target':
            self._adjust(row, 1, True)
        elif row.startswith('vm:'):
            alias = row[3:]
            self.picked ^= {alias}
        else:
            self.touched = False

    def _adjust(self, row, direction, small):
        self.touched = True
        if row == 'schedule':
            self.schedule_on = True
            hour, minute = (int(part) for part in self.at.split(':'))
            total = (hour * 60 + minute + direction * (15 if small else 60)) % (24 * 60)
            self.at = f'{total // 60:02d}:{total % 60:02d}'
        elif row == 'days':
            presets = [value for value, _ in autostop.DAY_PRESETS]
            index = presets.index(self.days) if self.days in presets else -1
            self.days = presets[(index + direction) % len(presets)]
        elif row == 'max':
            self.max_on = True
            self.max_hours = autostop.step(autostop.MAX_STEPS, self.max_hours, direction)
        elif row == 'idle':
            self.idle_on = True
            self.idle_minutes = autostop.step(autostop.IDLE_STEPS, self.idle_minutes, direction)
        elif row == 'idle_cpu':
            self.idle_cpu = autostop.step(autostop.CPU_STEPS, self.idle_cpu, direction)
        elif row == 'idle_ssh':
            self.idle_ssh = not self.idle_ssh
        elif row == 'once':
            if self.once_at and not self.once_touched:
                self.once_minutes = autostop.step(autostop.ONCE_STEPS,
                                                  max(1, int((self.once_at - time.time()) // 60)), direction)
            else:
                self.once_minutes = autostop.step(autostop.ONCE_STEPS, self.once_minutes, direction)
            self.once_on = True
            self.once_at = 0
            self.once_touched = True
        elif row == 'target':
            index = TARGETS.index(self.target)
            self.target = TARGETS[(index + direction) % len(TARGETS)]
        else:
            self.touched = False

    # -- preview ----------------------------------------------------------
    def preview(self, now=None):
        """``(epoch, reason)`` of the soonest concrete power-off with these values, or None."""
        now = time.time() if now is None else now
        view = self.view()
        boot = view.inst.started if view is not None and view.inst.started else now
        rules = self.rules()
        stamped = autostop.stamp(rules, self.loaded, int(now))
        options = []
        if rules.schedule_at:
            at = autostop.next_schedule(rules, max(boot, stamped.schedule_from))
            if at:
                options.append((at, 'schedule'))
        if rules.max_hours:
            options.append((max(boot, stamped.max_from) + rules.max_hours * 3600, 'max'))
        if self.once_on:
            options.append((self.once_at if self.once_at else now + self.once_minutes * 60, 'once'))
        options = [option for option in options if option[0] > now - 60]
        return min(options) if options else None

    def height(self) -> int:
        return len(self.rows()) + 10

    # -- drawing ----------------------------------------------------------
    def draw(self, canvas, palette, now=None):
        now = time.time() if now is None else now
        s = kit.Painter(palette)
        bg = 'surfaceContainerHigh'
        width, height = canvas.width, canvas.height
        canvas.fill(Rect(0, 0, width, height), ' ', s(bg=bg))
        box(canvas, Rect(0, 0, width, height), s('outlineVariant', bg),
            [(f' {kit.GLYPH["power"]} Apagado automático ', s('onSurface', bg, bold=True))])
        inner = max(0, width - 4)
        view = self.view()
        y = 2
        if view is not None:
            inst = view.inst
            parts = [inst.name]
            if inst.started:
                parts.append(f'encendida hace {autostop.fmt_duration(now - inst.started)}')
            parts.append(inst.zone)
            canvas.text(2, y, truncate(' · '.join(parts), inner), s('onSurfaceVariant', bg))
        if self.reading:
            note = 'leyendo la configuración de la VM…'
            canvas.text(max(2, width - 2 - len(note)), y, truncate(note, inner), s('tertiary', bg))
        y += 2

        selected = self.current()
        for row in self.rows():
            if y >= height - 6:
                break
            self._draw_row(canvas, s, row, y, row == selected, width, now)
            y += 1
        y += 1

        stop = self.preview(now)
        if y < height - 4:
            if stop is not None:
                text = (f'{kit.GLYPH["power"]} Se apaga {autostop.fmt_when(stop[0], now)} '
                        f'(en {autostop.fmt_duration(stop[0] - now)}) · {SHORT_REASON[stop[1]]}')
                if self.idle_on:
                    text += f' · o tras {self.idle_minutes} min sin uso'
                canvas.text(2, y, truncate(text, inner), s('primary', bg, bold=True))
            elif self.idle_on:
                canvas.text(2, y, truncate(f'{kit.GLYPH["power"]} Se apagará tras {self.idle_minutes} min sin uso',
                                           inner), s('primary', bg, bold=True))
            else:
                canvas.text(2, y, truncate('Sin apagado automático', inner), s('onSurfaceVariant', bg))
        y += 1
        if y < height - 3 and self.idle_on:
            uses = [f'CPU ≥ {self.idle_cpu} %']
            if self.idle_ssh:
                uses.append('SSH abierta')
            if self.idle_procs:
                uses.append('/'.join(self.idle_procs) + ' corriendo')
            text = 'En uso si hay ' + ', '.join(uses[:-1]) + (f' o {uses[-1]}' if len(uses) > 1 else uses[0])
            canvas.text(2, y, truncate(text, inner), s('onSurfaceVariant', bg))

        row_y = height - 2
        cancel = 'Esc cancelar'
        canvas.text(2, row_y, cancel, s('onSurfaceVariant', bg))
        count = len(self.targets())
        label = ' ⏎ Guardar ' if count <= 1 else f' ⏎ Guardar en {count} VMs '
        role = 'primary' if count else 'outline'
        canvas.text(2 + len(cancel) + 3, row_y, label,
                    s('onPrimary' if count else 'surface', role, bold=True))

    def _draw_row(self, canvas, s, row, y, selected, width, now):
        bg = 'surfaceContainerHighest' if selected else 'surfaceContainerHigh'
        canvas.fill(Rect(1, y, max(0, width - 2), 1), ' ', s(bg=bg))
        if selected:
            canvas.text(1, y, '▌', s('primary', bg))
        label_style = s('onSurface', bg, bold=selected)
        muted = s('onSurfaceVariant', bg)
        value_style = s('primary', bg, bold=True) if selected else s('onSurface', bg)
        x = 3
        value_x = x + LABEL_WIDTH
        room = max(0, width - value_x - 2)

        def switch(on, label, indent=0):
            canvas.text(x + indent, y, '●' if on else '○', s('primary' if on else 'outline', bg))
            canvas.text(x + indent + 2, y, truncate(label, LABEL_WIDTH - 2 - indent),
                        label_style if on or selected else muted)

        def value(text, adjustable=True, style=None):
            shown = f'‹ {text} ›' if selected and adjustable else text
            canvas.text(value_x, y, truncate(shown, room), style or value_style)
            return len(shown)

        def after(offset, text):
            if offset + 2 < room:
                canvas.text(value_x + offset + 2, y, truncate(text, room - offset - 2), muted)

        if row == 'schedule':
            switch(self.schedule_on, 'Horario fijo')
            if self.schedule_on:
                used = value(self.at)
                after(used, autostop.describe_days(self.days))
            else:
                value('desactivado', False, muted)
        elif row == 'days':
            canvas.text(x + 2, y, 'Días', label_style if selected else muted)
            for index, letter in enumerate(autostop.DAY_LETTERS):
                on = str(index + 1) in self.days
                canvas.text(value_x + index * 2, y, letter,
                            s('primary', bg, bold=True) if on else s('outline', bg))
            if selected:
                after(14, '1–7 un día · ←→ todos / lun–vie / fin de semana')
        elif row == 'max':
            switch(self.max_on, 'Tiempo máximo')
            if self.max_on:
                used = value(f'{self.max_hours} h')
                after(used, 'después de encenderse')
            else:
                value('desactivado', False, muted)
        elif row == 'idle':
            switch(self.idle_on, 'Sin actividad')
            if self.idle_on:
                used = value(f'{self.idle_minutes} min')
                after(used, 'sin uso')
            else:
                value('desactivado', False, muted)
        elif row == 'idle_cpu':
            canvas.text(x + 2, y, 'CPU por debajo de', label_style if selected else muted)
            value(f'{self.idle_cpu} %')
        elif row == 'idle_ssh':
            canvas.text(x + 2, y, 'SSH abierta = en uso', label_style if selected else muted)
            value('sí' if self.idle_ssh else 'no')
        elif row == 'once':
            switch(self.once_on, 'Una vez')
            if self.once_on and self.once_at:
                used = value(autostop.fmt_when(self.once_at, now))
                after(used, f'en {autostop.fmt_duration(self.once_at - now)} · ya programado')
            elif self.once_on:
                used = value(f'en {autostop.fmt_duration(self.once_minutes * 60)}')
                after(used, f'a las {autostop.fmt_when(now + self.once_minutes * 60, now)}')
            else:
                value('desactivado', False, muted)
        elif row == 'target':
            canvas.text(x + 2, y, 'Aplicar a', label_style)
            running = self.running()
            view = self.view()
            text = {'one': f'solo {view.inst.name if view else self.alias}',
                    'running': f'todas las encendidas ({len(running)})',
                    'pick': f'elegir VMs ({len(self.targets())} de {len(running)})'}[self.target]
            value(text)
        elif row.startswith('vm:'):
            alias = row[3:]
            other = self.view(alias)
            on = alias in self.picked
            canvas.text(x + 4, y, '☑' if on else '☐', s('primary' if on else 'outline', bg))
            name = other.inst.name if other else alias
            project = other.inst.project if other else ''
            canvas.text(x + 6, y, truncate(name, LABEL_WIDTH), label_style if on else muted)
            if project:
                canvas.text(value_x + 4, y, truncate(project, max(0, room - 4)), muted)
