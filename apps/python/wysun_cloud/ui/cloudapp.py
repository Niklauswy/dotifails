"""The Wysun Cloud app: cached first paint, live probes, transitions and actions.

:class:`CloudApp` joins everything the other modules produce: the gcloud inventory
(one refresh at a time, in a worker thread), the persistent SSH probes of every
running VM, the mosaic and detail screens as animatable layers, the confirmation
dialog, the toasts, the filter and the help overlay. The engine still owns the
clock; this module only reacts to keys, timers, children and probe samples.

Layout of the frame: one layer per VM (a card, an off line, or the detail screen
when its card is expanded), one layer per project title, and the header, footer,
modal, help and toast on top. Transitions move those layers' rectangles and
opacities with the ``anim`` tokens; under ``WYSUN_REDUCED_MOTION=1`` every tween
finishes at once.

Threads only run gcloud (``inventory.refresh``, ``operations``, ``firewall``,
``disks``) and Cloud Monitoring; their results are posted back with
``self.after(0, …)``. SSH probes and tab commands use ``App.spawn`` and therefore
the loop itself. No UI state is touched from a thread.
"""
from __future__ import annotations

import subprocess
import threading
import time
from collections import deque

from wysun_core.launch import terminal_argv
from wysun_core.tui.anim import (Rect, Tween, curve, duration, fade_steps,
                                 lerp_rect, reduced_motion)
from wysun_core.tui.app import App, Dim, Layer
from wysun_core.tui.canvas import Style
from wysun_core.tui.draw import box, truncate
from wysun_core.tui.keys import Key, Mouse

from wysun_cloud import cache, inventory, monitoring, ssh
from wysun_cloud.gcloud import Gcloud, GcloudError
from wysun_cloud.model import Instance, TabData
from wysun_cloud.ui import detail as detail_ui
from wysun_cloud.ui import mosaic as mosaic_ui
from wysun_cloud.ui.detail import HEADER_ROWS, TABS, DetailData
from wysun_cloud.ui.mosaic import VmView

__all__ = ['CloudApp']

REFRESH_SECONDS = 30
SPIN_SECONDS = 0.2
DOUBLE_CLICK = 0.4
REVEAL_LINES = 40
REVEAL_STEP = 0.014
TOAST_SECONDS = 2.6
TOAST_WIDTH = 80

STOP_COPY = 'El disco se conserva; la IP externa efímera cambiará.'
RESET_COPY = 'Es un reinicio forzado (reset): no espera a los procesos.'
BUSY_TEXT = {'start': 'encendiendo', 'stop': 'apagando', 'reset': 'reiniciando'}
PAST_TEXT = {'start': 'encendida', 'stop': 'apagada', 'reset': 'reiniciada'}
VERB_TEXT = {'start': 'Encender', 'stop': 'Apagar', 'reset': 'Reiniciar'}
MODAL_WIDTH = 56
MODAL_HEIGHT = 8

MOSAIC_HINTS = [
    ('←↑↓→', 'elegir'), ('⏎', 'detalle'), ('s', 'encender'), ('x', 'apagar'),
    ('r', 'reiniciar'), ('c', 'ssh'), ('/', 'filtrar'), ('?', 'ayuda'), ('q', 'salir'),
]
DETAIL_HINTS = [
    ('Esc', 'volver'), ('1-7', 'pestaña'), ('←→', 'pestaña'), ('x', 'apagar'),
    ('r', 'reiniciar'), ('c', 'ssh'),
]
MODAL_HINTS = [('⏎', 'confirmar'), ('Esc', 'cancelar')]

HELP_LINES = [
    ('←↑↓→', 'elegir la VM'),
    ('⏎', 'abrir el detalle'),
    ('Esc / q', 'volver al mosaico'),
    ('1-7', 'cambiar de pestaña'),
    ('← →', 'pestaña anterior / siguiente'),
    ('x', 'apagar (pide confirmación)'),
    ('r', 'reiniciar (pide confirmación)'),
    ('s', 'encender una VM apagada'),
    ('c', 'abrir SSH en una terminal'),
    ('h', '24 h / 7 días en Historial'),
    ('m', 'ordenar Procesos por CPU / RAM'),
    ('d', 'volver a calcular du en Disco'),
    ('/', 'filtrar por nombre'),
    ('p', 'buscar proyectos ahora'),
    ('?', 'esta ayuda'),
    ('q', 'salir'),
]


class _Panel(Layer):
    """A layer that delegates its drawing to a function of ``(canvas, palette)``."""

    def __init__(self, rect, draw, z=0, opacity=1.0, visible=True):
        super().__init__(rect, z=z, opacity=opacity, visible=visible)
        self._draw = draw

    def draw(self, canvas, palette):
        self._draw(canvas, palette)


class _VmLayer(Layer):
    """One VM: its mosaic card/off line, or the whole detail screen when expanded."""

    def __init__(self, app, alias, rect):
        super().__init__(rect, z=10)
        self.app = app
        self.alias = alias

    def draw(self, canvas, palette):
        app = self.app
        view = app._view(self.alias)
        if view is None:
            return
        local = Rect(0, 0, canvas.width, canvas.height)
        if (app.mode == 'detail' and app.detail_alias == self.alias
                and app.detail_content):
            app._draw_detail(canvas, view, palette)
        elif view.inst.running:
            mosaic_ui.draw_card(canvas, local, view, palette,
                                app.selected == self.alias and app.mode == 'mosaic',
                                app.spin)
        else:
            mosaic_ui.draw_off(canvas, local, view, palette,
                               app.selected == self.alias and app.mode == 'mosaic',
                               app.spin)


class CloudApp(App):
    """The full-screen Wysun Cloud terminal app."""

    def __init__(self, term=None, home=None, gcloud=None):
        super().__init__(term=term, home=home)
        self.gcloud = gcloud if gcloud is not None else Gcloud()
        self.views: list[VmView] = []
        self.projects: list[str] = []
        self.selected: str | None = None
        self.slot_rects: dict[str, Rect] = {}
        self.scroll: dict[str, int] = {}

        self.mode = 'mosaic'
        self.detail_alias: str | None = None
        self.detail_content = False
        self.detail_data: dict[str, DetailData] = {}
        self.tab = 0
        self.range_hours = 24
        self.sort = 'cpu'
        self.reveal: int | None = None
        self.tab_slide = 0
        self.detail_scroll = 0
        self._detail_total = 0
        self._tab_boxes: list[Rect] = []

        self.refreshing = False
        self.error_message: str | None = None
        self.stale = False
        self.loaded_at: float | None = None
        self.pending_relayout = False

        self.spin = 0
        self.filter = ''
        self.filter_active = False
        self.help_open = False
        self.modal: dict | None = None
        self.toast_text = ''
        self.help_layer: _Panel | None = None

        self.probes: dict[str, ssh.ProbeSession] = {}
        self._running: set[tuple[str, str]] = set()
        self._vm_layers: dict[str, _VmLayer] = {}
        self.title_layers: dict[str, _Panel] = {}
        self.header: _Panel | None = None
        self.footer: _Panel | None = None
        self.toast_layer: _Panel | None = None

        self.intro_done = False
        self.intro_running = False
        self._last_click: tuple[str, float] | None = None
        self._toast_timer = None

    # -- lifecycle --------------------------------------------------------
    def on_start(self) -> None:
        self._build_chrome()
        data = cache.load()
        if data:
            try:
                instances = [Instance.from_dict(item) for item in data.get('instances') or []
                             if isinstance(item, dict)]
            except (TypeError, ValueError):
                instances = []
            self.loaded_at = float(data.get('saved') or time.time())
            self._set_inventory([str(project) for project in data.get('projects') or []],
                                instances)
        self._refresh()
        self.every(SPIN_SECONDS, self._tick)
        self.every(REFRESH_SECONDS, self._refresh)

    def _shutdown(self) -> None:
        for session in list(self.probes.values()):
            session.stop()
        self.probes.clear()
        super()._shutdown()

    def on_theme(self) -> None:
        self.invalidate()

    def _tick(self) -> None:
        self.spin = (self.spin + 1) % 4
        self.invalidate()

    # -- chrome -----------------------------------------------------------
    def _build_chrome(self) -> None:
        width, height = self.size
        self.header = _Panel(Rect(0, 0, width, 1), self._draw_header, z=70)
        self.footer = _Panel(Rect(0, height - 1, width, 1), self._draw_footer, z=70)
        self.layers.extend([self.header, self.footer])
        self.toast_layer = _Panel(Rect(0, 0, 1, 1), self._draw_toast, z=130,
                                  visible=False)
        self.layers.append(self.toast_layer)

    def _draw_header(self, canvas, palette) -> None:
        width = canvas.width
        age = int(max(0.0, time.time() - self.loaded_at)) if self.loaded_at else 0
        right = '⟳ actualizando…' if self.refreshing else f'⟳ {age} s'
        view = self._view(self.detail_alias) if self.mode == 'detail' else None
        if view is not None:
            chip = ' ☁ Wysun Cloud '
            canvas.text(1, 0, chip, Style(fg=palette['onPrimary'], bg=palette['primary'],
                                         bold=True))
            path = f'  mosaico › {view.inst.project} › {view.inst.name}'
            room = max(0, width - 1 - len(chip) - len(right) - 2)
            canvas.text(1 + len(chip), 0, truncate(path, room),
                        Style(fg=palette['onSurfaceVariant']))
            if len(right) <= width - 2:
                canvas.text(width - 1 - len(right), 0, right,
                            Style(fg=palette['onSurfaceVariant']))
            return
        mosaic_ui.draw_header(canvas, width, self.views, palette, age, self.refreshing)

    def _draw_footer(self, canvas, palette) -> None:
        if self.filter_active:
            text = f'Filtro: {self.filter}▏'
            canvas.text(1, 0, truncate(text, max(0, canvas.width - 2)),
                        Style(fg=palette['primary'], bold=True))
            hint = 'Esc borrar · ⏎ aplicar'
            if len(hint) + 2 < canvas.width:
                canvas.text(canvas.width - 1 - len(hint), 0, hint,
                            Style(fg=palette['onSurfaceVariant']))
            return
        if self.modal is not None:
            hints = MODAL_HINTS
        elif self.mode == 'detail':
            hints = list(DETAIL_HINTS)
            if self.tab == 6:
                hints.append(('h', '24 h / 7 d'))
        else:
            hints = MOSAIC_HINTS
        mosaic_ui.draw_footer(canvas, canvas.width, 1, hints, palette)

    def _draw_toast(self, canvas, palette) -> None:
        canvas.fill(Rect(0, 0, canvas.width, canvas.height), ' ',
                    Style(bg=palette['surfaceContainerHigh']))
        box(canvas, Rect(0, 0, canvas.width, canvas.height),
            Style(fg=palette['outlineVariant']))
        text = truncate(self.toast_text, max(0, canvas.width - 4))
        canvas.text(1, 0, '●', Style(fg=palette['primary']))
        canvas.text(3, 0, text, Style(fg=palette['onSurface']))

    # -- inventory and refresh -------------------------------------------
    def _refresh(self, discover: bool = False) -> None:
        if self.refreshing:
            return
        self.refreshing = True
        self.invalidate()

        def work():
            try:
                result = inventory.refresh(self.gcloud, time.time(), discover=discover)
            except GcloudError as error:
                message = error.message
                self.after(0, lambda message=message: self._refresh_failed(message))
            except Exception as error:                       # never a traceback on screen
                message = str(error) or 'gcloud falló'
                self.after(0, lambda message=message: self._refresh_failed(message))
            else:
                self.after(0, lambda result=result: self._refresh_done(*result))

        threading.Thread(target=work, daemon=True).start()

    def _refresh_failed(self, message: str) -> None:
        self.refreshing = False
        self.error_message = message
        self.stale = bool(self.views)
        self.invalidate()

    def _refresh_done(self, projects, instances, messages) -> None:
        self.refreshing = False
        self.loaded_at = time.time()
        if messages and not instances and self.views:
            # Nothing answered: keep what the last good refresh painted.
            self.error_message = next(iter(messages.values()))
            self.stale = True
            self.invalidate()
            return
        self.error_message = next(iter(messages.values())) if messages else None
        self.stale = bool(messages)
        self._set_inventory(list(projects), list(instances))
        self.invalidate()

    # -- views and layers -------------------------------------------------
    def _view(self, alias: str | None) -> VmView | None:
        if alias is None:
            return None
        for view in self.views:
            if view.inst.alias == alias:
                return view
        return None

    def _new_view(self, inst: Instance) -> VmView:
        view = VmView(inst=inst, sample=None,
                      state='conectando' if inst.running else 'sin-ssh')
        view.rx_hist = deque(maxlen=120)
        view.tx_hist = deque(maxlen=120)
        return view

    def _add_vm_layer(self, alias: str) -> None:
        if alias in self._vm_layers:
            return
        layer = _VmLayer(self, alias, Rect(0, 0, 1, 1))
        self._vm_layers[alias] = layer
        self.layers.append(layer)

    def _set_inventory(self, projects: list[str], instances: list[Instance]) -> None:
        # A refresh lands between frames: snap whatever transition was running so the
        # new rectangles are not fought over by a tween with stale targets.
        self.animator.finish_all()
        if self.intro_running:
            self.intro_running = False
            self.intro_done = True
        previous = {view.inst.alias: view for view in self.views}
        views = []
        for inst in instances:
            view = previous.get(inst.alias)
            if view is None:
                view = self._new_view(inst)
                self._add_vm_layer(inst.alias)
            view.inst = inst
            views.append(view)
        self.views = views
        known = {view.inst.alias for view in views}
        for alias in list(self._vm_layers):
            if alias not in known:
                layer = self._vm_layers.pop(alias)
                if layer in self.layers:
                    self.layers.remove(layer)
                self._stop_probe(alias)

        ordered = list(dict.fromkeys(str(project) for project in projects))
        for view in views:
            if view.inst.project not in ordered:
                ordered.append(view.inst.project)
        self.projects = ordered
        self._sync_titles()

        aliases = [view.inst.alias for view in views]
        if self.selected not in aliases:
            running = [view.inst.alias for view in views if view.inst.running]
            self.selected = (running or aliases or [None])[0]

        if self.detail_alias is not None:
            view = self._view(self.detail_alias)
            if view is None or not view.inst.running:
                self._close_detail(snap=True)

        self._sync_probes()
        animate = self.pending_relayout
        self.pending_relayout = False
        self._apply_layout(snap=not animate, animate=animate)
        if not self.intro_done and views:
            self._start_intro()
        self.invalidate()

    def _sync_titles(self) -> None:
        for project in self.projects:
            if project in self.title_layers:
                continue
            def draw(canvas, palette, project=project):
                canvas.text(0, 0, truncate(project, canvas.width),
                            Style(fg=palette['onSurface'], bold=True))
            layer = _Panel(Rect(0, 0, 1, 1), draw, z=20)
            self.title_layers[project] = layer
            self.layers.append(layer)
        for project in list(self.title_layers):
            if project in self.projects:
                continue
            layer = self.title_layers.pop(project)
            if layer in self.layers:
                self.layers.remove(layer)

    # -- probes -----------------------------------------------------------
    def _sync_probes(self) -> None:
        for view in self.views:
            alias = view.inst.alias
            if view.inst.running:
                if alias not in self.probes:
                    self._start_probe(view)
            else:
                self._stop_probe(alias)

    def _start_probe(self, view: VmView) -> None:
        alias = view.inst.alias

        def sample(sample):
            current = self._view(alias)
            if current is None or not current.inst.running:
                return
            current.sample = sample
            current.cpu_hist.append(sample.cpu)
            current.rx_hist.append(sample.rx_mbs)
            current.tx_hist.append(sample.tx_mbs)
            self.invalidate()

        def state(state, reason):
            current = self._view(alias)
            if current is None:
                return
            current.state = state
            current.reason = reason
            self.invalidate()

        session = ssh.ProbeSession(self, view.inst, sample, state)
        self.probes[alias] = session
        try:
            session.start()
        except OSError:                          # gcloud or ssh is not installed
            self.probes.pop(alias, None)

    def _stop_probe(self, alias: str) -> None:
        session = self.probes.pop(alias, None)
        if session is not None:
            session.stop()

    # -- layout -----------------------------------------------------------
    def _visible_views(self) -> list[VmView]:
        if not self.filter:
            return list(self.views)
        needle = self.filter.lower()
        return [view for view in self.views if needle in view.inst.name.lower()]

    def _visible_projects(self) -> list[str]:
        if not self.filter:
            return list(self.projects)
        keep = {view.inst.project for view in self._visible_views()}
        return [project for project in self.projects if project in keep]

    def _layout_rects(self) -> dict[str, Rect]:
        width, height = self.size
        return mosaic_ui.layout(self._visible_views(), self._visible_projects(),
                                width, height, scroll=self.scroll,
                                selected=self.selected)

    def _detail_rect(self) -> Rect:
        width, height = self.size
        return Rect(0, 2, width, max(0, height - 3))

    def _apply_layout(self, snap: bool = True, animate: bool = False) -> None:
        width, height = self.size
        rects = self._layout_rects()
        self.slot_rects = rects
        titles = mosaic_ui.project_titles(self._visible_views(), self._visible_projects(),
                                          width, height, scroll=self.scroll,
                                          selected=self.selected)
        ordered = sorted(titles.items(), key=lambda item: (item[1][1], item[1][0]))
        for index, (project, (x, y)) in enumerate(ordered):
            layer = self.title_layers.get(project)
            if layer is None:
                continue
            if index + 1 < len(ordered) and ordered[index + 1][1][1] == y:
                next_x = ordered[index + 1][1][0]
                column_width = max(1, next_x - x - mosaic_ui.GAP)
            else:
                column_width = max(1, width - x - 1)
            layer.rect = Rect(x, y, column_width, 1)
            layer.visible = True
            layer.opacity = 1.0
        for project, layer in self.title_layers.items():
            if project not in titles:
                layer.visible = False

        if self.mode == 'detail' and self.detail_alias is not None:
            for layer in self.title_layers.values():
                layer.visible = False
            for alias, layer in self._vm_layers.items():
                if alias == self.detail_alias:
                    layer.rect = self._detail_rect()
                    layer.visible = True
                    layer.opacity = 1.0
                    layer.z = 60
                else:
                    layer.visible = False
            return

        snap = snap or reduced_motion()
        for alias, layer in self._vm_layers.items():
            target = rects.get(alias)
            if target is None:
                layer.visible = False
                layer.opacity = 1.0
                continue
            layer.visible = True
            layer.opacity = 1.0
            layer.z = 10
            if animate and not snap:
                start = layer.rect
                self.animator.add(Tween(
                    duration('normal'), curve('standard'),
                    lambda t, start=start, target=target, layer=layer:
                    setattr(layer, 'rect', lerp_rect(start, target, t))))
            else:
                layer.rect = target
        if animate and not snap:
            self.invalidate()

    # -- intro ------------------------------------------------------------
    def _start_intro(self) -> None:
        self.intro_done = True
        if reduced_motion():
            return
        items = [layer for layer in self.title_layers.values() if layer.visible]
        items.extend(layer for layer in self._vm_layers.values() if layer.visible)
        items.sort(key=lambda layer: (layer.rect.y, layer.rect.x))
        if not items:
            return
        self.intro_running = True
        for index, layer in enumerate(items):
            target = layer.rect
            layer.rect = Rect(target.x, target.y + 2, target.w, target.h)
            layer.opacity = 0.0
            self.after(index * 0.045, lambda layer=layer, target=target:
                       self._intro_step(layer, target))
        self.after(len(items) * 0.045 + duration('expressiveDefaultEffects') + 0.05,
                   self._intro_finish)

    def _intro_step(self, layer, target) -> None:
        if not self.intro_running:
            return
        start = layer.rect
        self.animator.add(Tween(
            duration('expressiveDefaultEffects'), curve('emphasizedDecel'),
            lambda t, layer=layer, start=start, target=target: (
                setattr(layer, 'rect', lerp_rect(start, target, t)),
                setattr(layer, 'opacity', fade_steps(t)))))
        self.invalidate()

    def _intro_finish(self) -> None:
        self.intro_running = False
        for layer in list(self.title_layers.values()) + list(self._vm_layers.values()):
            layer.opacity = 1.0
        self.invalidate()

    # -- detail -----------------------------------------------------------
    def _open_detail(self, alias: str) -> None:
        view = self._view(alias)
        if view is None or not view.inst.running:
            return
        self.animator.finish_all()
        self.mode = 'detail'
        self.detail_alias = alias
        self.detail_content = False
        self.tab = 0
        self.tab_slide = 0
        self.detail_scroll = 0
        self.reveal = 0
        self._running = {key for key in self._running if key[0] != alias}
        # On-demand data is read again on every open (the plan's "once per open").
        self.detail_data.pop(alias, None)
        self._detail(alias)
        layer = self._vm_layers.get(alias)
        if layer is None:
            return
        layer.z = 60
        layer.visible = True
        layer.opacity = 1.0
        target = self._detail_rect()
        others = [other for name, other in self._vm_layers.items() if name != alias]
        others.extend(self.title_layers.values())
        for other in others:
            other.visible = True
            other.opacity = 1.0
        if reduced_motion():
            layer.rect = target
            self._detail_opened(alias, others)
            self.invalidate()
            return
        start = layer.rect

        def step(t):
            layer.rect = lerp_rect(start, target, t)

        def fade(t):
            opacity = fade_steps(max(0.0, 1.0 - t))
            for other in others:
                other.opacity = opacity

        def done():
            layer.rect = target
            self._detail_opened(alias, others)

        self.animator.add(Tween(duration('expressiveFastEffects'),
                                curve('expressiveFastEffects'), fade))
        self.animator.add(Tween(duration('expressiveDefaultSpatial'),
                                curve('emphasizedDecel'), step, done))
        self.invalidate()

    def _detail_opened(self, alias: str, others) -> None:
        if self.detail_alias != alias:
            return
        self.detail_content = True
        for other in others:
            other.visible = False
            other.opacity = 1.0
        self._load_tab_data(0, alias)
        if reduced_motion():
            self.reveal = None
        else:
            self.reveal = 0

            def step(t):
                self.reveal = max(1, int(round(t * REVEAL_LINES)))

            # Linear so consecutive lines appear 14 ms apart, as the prototype.
            self.animator.add(Tween(REVEAL_LINES * REVEAL_STEP, lambda t: t,
                                    step, lambda: setattr(self, 'reveal', None)))
        self.invalidate()

    def _close_detail(self, snap: bool = False) -> None:
        alias = self.detail_alias
        if alias is None:
            return
        self.animator.finish_all()
        layer = self._vm_layers.get(alias)
        self.detail_content = False
        self.reveal = None
        self.tab_slide = 0
        self._tab_boxes = []
        others = [other for name, other in self._vm_layers.items() if name != alias]
        others.extend(self.title_layers.values())

        def finish():
            self.mode = 'mosaic'
            self.detail_alias = None
            self.reveal = None
            if layer is not None:
                layer.z = 10
            for other in others:
                other.visible = True
                other.opacity = 1.0
            self._apply_layout(snap=True)
            self.invalidate()

        target = self._layout_rects().get(alias)
        if layer is None or target is None:
            finish()
            return
        if snap or reduced_motion():
            layer.rect = target
            finish()
            return
        start = layer.rect
        body_rows = max(1, self.size[1] - 2 - HEADER_ROWS)
        self.reveal = body_rows
        for other in others:
            other.visible = True
            other.opacity = 0.0

        def step(t):
            layer.rect = lerp_rect(start, target, t)
            self.reveal = max(0, int(round((1.0 - t) * body_rows)))

        def fade(t):
            opacity = fade_steps(min(1.0, t))
            for other in others:
                other.opacity = opacity

        self.animator.add(Tween(duration('expressiveFastEffects'),
                                curve('expressiveFastEffects'), fade))
        self.animator.add(Tween(duration('expressiveDefaultSpatial'),
                                curve('emphasizedDecel'), step, finish))
        self.invalidate()

    def _detail(self, alias: str) -> DetailData:
        data = self.detail_data.get(alias)
        if data is None:
            data = DetailData()
            self.detail_data[alias] = data
        return data

    # -- tab data ---------------------------------------------------------
    def _load_tab_data(self, tab: int, alias: str | None) -> None:
        if alias is None:
            return
        if tab in (0, 4):
            self._ensure_tab(alias, 'failed')
            self._ensure_tab(alias, 'docker')
        if tab in (0, 5):
            self._ensure_tab(alias, 'journal')
        if tab == 3:
            self._ensure_tab(alias, 'ports')
            self._ensure_gcloud(alias, 'firewall')
        if tab == 2:
            self._ensure_tab(alias, 'du')
            self._ensure_gcloud(alias, 'disks')
        if tab == 6:
            self._ensure_history(alias, 24)
            self._ensure_gcloud(alias, 'operations')

    def _ensure_tab(self, alias: str, kind: str) -> None:
        data = self._detail(alias)
        key = (alias, kind)
        if kind in data.tabs or key in self._running:
            return
        view = self._view(alias)
        if view is None:
            return
        self._running.add(key)

        def done(result):
            self._running.discard(key)
            data.tabs[kind] = result
            if result.error:
                data.errors[kind] = result.error
            else:
                data.errors.pop(kind, None)
            self.invalidate()

        try:
            ssh.run_tab_command(self, view.inst, kind, done)
        except OSError:                          # ssh or gcloud is not installed
            self._running.discard(key)
            done(TabData(kind=kind, lines=[], error='no se pudo ejecutar ssh'))

    def _ensure_gcloud(self, alias: str, kind: str) -> None:
        data = self._detail(alias)
        key = (alias, kind)
        if getattr(data, kind) is not None or key in self._running:
            return
        view = self._view(alias)
        if view is None:
            return
        call = {'firewall': lambda: self.gcloud.firewall(view.inst),
                'disks': lambda: self.gcloud.disks(view.inst),
                'operations': lambda: self.gcloud.operations(view.inst)}[kind]

        def apply(value):
            setattr(data, kind, value)
            data.errors.pop(kind, None)

        self._gcloud_async(alias, key, call, apply)

    def _ensure_history(self, alias: str, hours: int) -> None:
        data = self._detail(alias)
        if data.history is None:
            data.history = {}
        if data.history.get(hours) is not None:
            return
        key = (alias, f'history{hours}')
        if key in self._running:
            return
        view = self._view(alias)
        if view is None:
            return

        def apply(points):
            data.history = data.history or {}
            data.history[hours] = points
            data.errors.pop('history', None)

        self._gcloud_async(alias, key,
                           lambda: monitoring.cpu_history(self.gcloud, view.inst, hours),
                           apply)

    def _gcloud_async(self, alias: str, key, call, apply) -> None:
        self._running.add(key)

        def work():
            try:
                outcome = ('ok', call())
            except GcloudError as error:
                outcome = ('err', error.message)
            except Exception as error:                   # never a traceback on screen
                outcome = ('err', str(error) or 'gcloud falló')
            self.after(0, lambda outcome=outcome: finish(outcome))

        def finish(outcome):
            self._running.discard(key)
            data = self._detail(alias)
            if outcome[0] == 'ok':
                apply(outcome[1])
            else:
                data.errors[key[1]] = outcome[1]
            self.invalidate()

        threading.Thread(target=work, daemon=True).start()

    # -- tabs -------------------------------------------------------------
    def _set_tab(self, index: int) -> None:
        index = max(0, min(len(TABS) - 1, int(index)))
        if self.detail_alias is None:
            return
        if index == self.tab:
            self._load_tab_data(index, self.detail_alias)
            return
        self.animator.finish_all()
        direction = 1 if index > self.tab else -1
        alias = self.detail_alias

        def out_step(t):
            self.tab_slide = -direction * int(round(t * 8))

        def switch():
            self.tab = index
            self.detail_scroll = 0
            self.tab_slide = 0
            self._load_tab_data(index, alias)

            def in_step(inner):
                self.tab_slide = direction * int(round((1.0 - inner) * 8))

            self.animator.add(Tween(duration('small'), curve('standard'), in_step))
            self.invalidate()

        self.animator.add(Tween(duration('small'), curve('standard'), out_step, switch))
        self.invalidate()

    # -- actions ----------------------------------------------------------
    def _start_action(self, view: VmView, verb: str) -> None:
        if view.busy is not None:
            return
        alias = view.inst.alias
        view.busy = BUSY_TEXT[verb]
        self.invalidate()
        argv = [self.gcloud.executable, *self.gcloud.action_argv(verb, view.inst), '--quiet']
        holder = {}

        def done(code):
            self._action_done(alias, verb, code, holder.get('child'))

        try:
            holder['child'] = self.spawn(argv, lambda line: None, done)
        except OSError:
            view.busy = None
            self._toast('No encontré gcloud')
            self.invalidate()

    def _action_done(self, alias: str, verb: str, code: int, child) -> None:
        view = self._view(alias)
        if view is not None:
            view.busy = None
        name = view.inst.name if view is not None else alias.split('.')[0]
        if code == 0:
            self._toast(f'{name} {PAST_TEXT[verb]}')
            self.pending_relayout = True
            self._refresh()
            return
        last = ''
        if child is not None and child.stderr_tail:
            last = child.stderr_tail[-1].strip()
        self._toast(truncate(last or 'gcloud falló', TOAST_WIDTH))
        self.invalidate()

    def _launch_ssh(self, view: VmView) -> None:
        argv = terminal_argv(ssh.ssh_command(view.inst, []))
        if argv is None:
            self._toast('No encontré una terminal')
            return
        try:
            subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self._toast('No encontré una terminal')

    # -- modal ------------------------------------------------------------
    def _modal_rect(self) -> Rect:
        width, height = self.size
        w = min(MODAL_WIDTH, max(10, width - 4))
        h = min(MODAL_HEIGHT, max(4, height - 2))
        return Rect(max(0, (width - w) // 2), max(0, (height - h) // 2), w, h)

    def _open_modal(self, verb: str, view: VmView) -> None:
        if self.modal is not None:
            return
        self.animator.finish_all()
        width, height = self.size
        target = self._modal_rect()
        start = Rect(target.x + target.w // 2 - 1, target.y + 3, 2, 1)
        backdrop = Dim(Rect(0, 0, width, height), 'scrim', z=100, opacity=0.0)
        panel = _Panel(start, self._draw_modal, z=110)
        self.modal = {'verb': verb, 'alias': view.inst.alias, 'backdrop': backdrop,
                      'layer': panel, 'start': start, 'target': target}
        self.layers.extend([backdrop, panel])
        self.invalidate()
        if reduced_motion():
            self._modal_geometry(1.0)
            return
        self.animator.add(Tween(duration('expressiveFastSpatial'),
                                curve('expressiveFastSpatial'), self._modal_geometry))
        self.invalidate()

    def _modal_geometry(self, t: float) -> None:
        modal = self.modal
        if modal is None:
            return
        progress = fade_steps(max(0.0, min(1.0, t)))
        modal['backdrop'].opacity = 0.45 * progress
        modal['layer'].rect = lerp_rect(modal['start'], modal['target'], t)
        self.invalidate()

    def _close_modal(self, confirm: bool) -> None:
        modal = self.modal
        if modal is None:
            return
        self.animator.finish_all()
        verb = modal['verb']
        alias = modal['alias']

        def finish():
            for key in ('backdrop', 'layer'):
                layer = modal.get(key)
                if layer is not None and layer in self.layers:
                    self.layers.remove(layer)
            self.modal = None
            self.invalidate()
            if confirm:
                view = self._view(alias)
                if view is not None:
                    self._start_action(view, verb)

        if reduced_motion():
            finish()
            return

        def step(t):
            self._modal_geometry(1.0 - t)

        self.animator.add(Tween(duration('expressiveFastEffects'),
                                curve('expressiveFastEffects'), step, finish))
        self.invalidate()

    def _draw_modal(self, canvas, palette) -> None:
        modal = self.modal
        if modal is None:
            return
        view = self._view(modal['alias'])
        if view is None:
            return
        canvas.fill(Rect(0, 0, canvas.width, canvas.height), ' ',
                    Style(bg=palette['surfaceContainerHigh']))
        box(canvas, Rect(0, 0, canvas.width, canvas.height),
            Style(fg=palette['primary']))
        verb = modal['verb']
        name = view.inst.name
        width = max(0, canvas.width - 4)
        title = truncate(f'¿{VERB_TEXT[verb]} {name}?', width)
        canvas.text(2, 1, title, Style(fg=palette['onSurface'], bold=True))
        copy = RESET_COPY if verb == 'reset' else STOP_COPY
        canvas.text(2, 3, truncate(copy, width),
                    Style(fg=palette['onSurfaceVariant']))
        sample = view.sample
        if sample is not None:
            sessions = 1 if view.state == 'activo' else 0
            label = 'sesión SSH abierta' if sessions == 1 else 'sesiones SSH abiertas'
            detail = f'{len(sample.top)} procesos · {sessions} {label}'
        else:
            detail = 'Sin sesión SSH abierta'
        canvas.text(2, 4, truncate(detail, width),
                    Style(fg=palette['onSurfaceVariant'], dim=True))
        row = 6
        if row < canvas.height:
            cancel = 'Esc cancelar'
            canvas.text(2, row, cancel,
                        Style(fg=palette['onSurfaceVariant'], dim=True))
            action = f' ⏎ {VERB_TEXT[verb]} '
            canvas.text(2 + len(cancel) + 3, row, action,
                        Style(fg=palette['onPrimary'], bg=palette['primary'], bold=True))

    # -- help -------------------------------------------------------------
    def _toggle_help(self, open: bool) -> None:
        if open and self.help_layer is None:
            width, height = self.size
            w = min(52, max(20, width - 4))
            h = min(len(HELP_LINES) + 3, max(6, height - 2))
            rect = Rect(max(0, (width - w) // 2), max(0, (height - h) // 2), w, h)
            self.help_layer = _Panel(rect, self._draw_help, z=120)
            self.layers.append(self.help_layer)
            self.help_open = True
        elif not open and self.help_layer is not None:
            if self.help_layer in self.layers:
                self.layers.remove(self.help_layer)
            self.help_layer = None
            self.help_open = False
        self.invalidate()

    def _draw_help(self, canvas, palette) -> None:
        canvas.fill(Rect(0, 0, canvas.width, canvas.height), ' ',
                    Style(bg=palette['surfaceContainerHigh']))
        box(canvas, Rect(0, 0, canvas.width, canvas.height),
            Style(fg=palette['outlineVariant']), title_segments=[
                (' Ayuda ', Style(fg=palette['onSurface'], bold=True))])
        key_style = Style(fg=palette['primary'], bold=True)
        label_style = Style(fg=palette['onSurfaceVariant'])
        for index, (key, label) in enumerate(HELP_LINES):
            row = 1 + index
            if row >= canvas.height - 1:
                break
            canvas.text(2, row, truncate(key, 9), key_style)
            canvas.text(12, row, truncate(label, max(0, canvas.width - 14)),
                        label_style)

    # -- toast ------------------------------------------------------------
    def _toast(self, text: str) -> None:
        self.toast_text = text
        if self.toast_layer is None:
            return
        self._place_toast()
        self.toast_layer.visible = True
        self.toast_layer.opacity = 1.0
        if self._toast_timer is not None:
            self.cancel(self._toast_timer)
            self._toast_timer = None
        if not reduced_motion():
            self.toast_layer.opacity = 0.0
            self.animator.add(Tween(duration('expressiveFastEffects'),
                                    curve('standardDecel'),
                                    lambda t: setattr(self.toast_layer, 'opacity',
                                                      fade_steps(t))))
        self._toast_timer = self.after(TOAST_SECONDS, self._hide_toast)
        self.invalidate()

    def _hide_toast(self) -> None:
        self._toast_timer = None
        if self.toast_layer is None:
            return
        if reduced_motion():
            self.toast_layer.visible = False
            self.invalidate()
            return

        def done():
            if self.toast_layer is not None:
                self.toast_layer.visible = False
            self.invalidate()

        self.animator.add(Tween(duration('expressiveFastEffects'),
                                curve('standardAccel'),
                                lambda t: setattr(self.toast_layer, 'opacity',
                                                  fade_steps(1.0 - t)), done))

    def _place_toast(self, snap: bool = True) -> None:
        if self.toast_layer is None:
            return
        width, height = self.size
        box_width = min(max(10, len(self.toast_text) + 6), max(10, width - 4))
        x = max(0, width - box_width - 2)
        y = max(0, height - 3)
        self.toast_layer.rect = Rect(x, y, box_width, 1)

    # -- input ------------------------------------------------------------
    def on_key(self, event: Key) -> None:
        if event.ctrl and event.name == 'c':
            self.quit()
            return
        if self.animator:
            self.animator.finish_all()
        if self.modal is not None:
            if event.name == 'enter':
                self._close_modal(True)
            elif event.name == 'escape':
                self._close_modal(False)
            return
        if self.help_open:
            if event.name in ('escape', 'q') or (event.name == 'char' and event.char == '?'):
                self._toggle_help(False)
            return
        if self.filter_active:
            self._filter_key(event)
            return
        if self.mode == 'detail':
            self._detail_key(event)
        else:
            self._mosaic_key(event)

    def _filter_key(self, event: Key) -> None:
        if event.name == 'escape':
            self.filter = ''
            self.filter_active = False
            self._filter_changed()
        elif event.name == 'enter':
            self.filter_active = False
            self.invalidate()
        elif event.name == 'backspace':
            self.filter = self.filter[:-1]
            self._filter_changed()
        elif event.name == 'char' and event.char and event.char.isprintable():
            self.filter += event.char
            self._filter_changed()
        else:
            return
        self.invalidate()

    def _filter_changed(self) -> None:
        aliases = [view.inst.alias for view in self._visible_views()]
        if self.selected not in aliases:
            self.selected = aliases[0] if aliases else None
        self._apply_layout(snap=True)

    def _mosaic_key(self, event: Key) -> None:
        name = event.name
        if name in ('up', 'down', 'left', 'right', 'home', 'end'):
            width, height = self.size
            target = mosaic_ui.navigate(self._visible_views(), self._visible_projects(),
                                        self.selected, name, width, height)
            if target:
                self.selected = target
                self._apply_layout(snap=True)
                self.invalidate()
            return
        if name == 'enter':
            view = self._view(self.selected)
            if view is not None and view.inst.running:
                self._open_detail(view.inst.alias)
            return
        if name != 'char':
            return
        key = event.char
        view = self._view(self.selected)
        if key == 'q':
            self.quit()
        elif key == 's':
            if view is not None and not view.inst.running:
                self._start_action(view, 'start')
        elif key == 'x':
            if view is not None and view.inst.running:
                self._open_modal('stop', view)
        elif key == 'r':
            if view is not None and view.inst.running:
                self._open_modal('reset', view)
        elif key == 'c':
            if view is not None and view.inst.running:
                self._launch_ssh(view)
        elif key == '/':
            self.filter_active = True
            self.filter = ''
            self._filter_changed()
            self.invalidate()
        elif key == '?':
            self._toggle_help(True)
        elif key == 'p':
            self._refresh(discover=True)

    def _detail_key(self, event: Key) -> None:
        name = event.name
        view = self._view(self.detail_alias)
        if view is None:
            self._close_detail()
            return
        if name in ('escape', 'backspace'):
            self._close_detail()
            return
        if name == 'left':
            self._set_tab(self.tab - 1)
            return
        if name == 'right' or name == 'tab':
            self._set_tab(self.tab + 1)
            return
        if name == 'backtab':
            self._set_tab(self.tab - 1)
            return
        if name != 'char':
            return
        key = event.char
        if key == 'q':
            self._close_detail()
        elif key in '1234567' and len(key) == 1:
            self._set_tab(int(key) - 1)
        elif key == 'x' and view.inst.running:
            self._open_modal('stop', view)
        elif key == 'r' and view.inst.running:
            self._open_modal('reset', view)
        elif key == 'c' and view.inst.running:
            self._launch_ssh(view)
        elif key == 'h' and self.tab == 6:
            self.range_hours = 168 if self.range_hours == 24 else 24
            self._ensure_history(self.detail_alias, self.range_hours)
            self.detail_scroll = 0
            self.invalidate()
        elif key == 'm' and self.tab == 1:
            self.sort = 'ram' if self.sort == 'cpu' else 'cpu'
            self.invalidate()
        elif key == 'd' and self.tab == 2 and (self.detail_alias, 'du') not in self._running:
            self._detail(self.detail_alias).tabs.pop('du', None)   # recalculate on demand
            self._ensure_tab(self.detail_alias, 'du')
            self.invalidate()

    def on_mouse(self, event: Mouse) -> None:
        if self.modal is not None or self.help_open:
            return
        if event.kind in ('wheelup', 'wheeldown'):
            self._wheel(-1 if event.kind == 'wheelup' else 1, event.x, event.y)
            return
        if event.kind != 'press':
            return
        if self.mode == 'detail':
            for index, tab_box in enumerate(self._tab_boxes):
                if (tab_box.x <= event.x < tab_box.x + tab_box.w
                        and tab_box.y <= event.y < tab_box.y + tab_box.h):
                    self._set_tab(index)
                    return
            return
        alias = self._hit_alias(event.x, event.y)
        if alias is None:
            return
        now = time.monotonic()
        view = self._view(alias)
        double = (self._last_click is not None
                  and self._last_click[0] == alias
                  and now - self._last_click[1] <= DOUBLE_CLICK)
        self.selected = alias
        if double and view is not None and view.inst.running:
            self._last_click = None
            self._apply_layout(snap=True)
            self._open_detail(alias)
            return
        self._last_click = (alias, now)
        self._apply_layout(snap=True)
        self.invalidate()

    def _hit_alias(self, x: int, y: int) -> str | None:
        for alias, rect in self.slot_rects.items():
            if rect.x <= x < rect.x + rect.w and rect.y <= y < rect.y + rect.h:
                return alias
        return None

    def _wheel(self, step: int, x: int, y: int) -> None:
        if self.mode == 'detail':
            view = self._view(self.detail_alias)
            if view is None:
                return
            body_height = max(0, self.size[1] - 2 - HEADER_ROWS)
            limit = max(0, self._detail_total - body_height)
            self.detail_scroll = max(0, min(limit, self.detail_scroll + step * 2))
            self.invalidate()
            return
        key = self._scroll_key_at(x, y)
        if key is None:
            return
        self.scroll[key] = max(0, self.scroll.get(key, 0) + step * 2)
        self._apply_layout(snap=True)
        self.invalidate()

    def _scroll_key_at(self, x: int, y: int) -> str | None:
        width, height = self.size
        views = self._visible_views()
        projects = self._visible_projects()
        if mosaic_ui._stacked(projects, width):        # the layout's own narrow mode
            return mosaic_ui.STACK_KEY
        columns = mosaic_ui._geometry(views, projects, width, height)[0]
        for column in columns:
            if column.x <= x < column.x + column.w:
                return column.key
        return None

    # -- painting ---------------------------------------------------------
    def draw(self, canvas) -> None:
        if self.error_message:
            suffix = ' · sin actualizar' if self.stale else ''
            text = truncate(self.error_message + suffix, max(0, canvas.width - 2))
            canvas.text(1, 1, text, Style(fg=self.palette['error']))

    def _draw_detail(self, canvas, view: VmView, palette) -> None:
        width, height = canvas.width, canvas.height
        header_height = min(HEADER_ROWS, height)
        boxes = detail_ui.draw_detail_header(
            canvas, Rect(0, 0, width, header_height), view, palette, self.tab,
            self._badges(palette))
        rect = self._vm_layers[view.inst.alias].rect if view.inst.alias in self._vm_layers else Rect(0, 0, 0, 0)
        self._tab_boxes = [Rect(rect.x + tab_box.x, rect.y + tab_box.y,
                                tab_box.w, tab_box.h) for tab_box in boxes]
        body_height = max(0, height - HEADER_ROWS)
        if body_height <= 0:
            self._detail_total = 0
            return
        visible = body_height
        if self.reveal is not None:
            visible = max(0, min(body_height, self.reveal))
        if visible <= 0:
            self._detail_total = 0
            return
        body = Rect(self.tab_slide, HEADER_ROWS, width, visible)
        total = detail_ui.draw_tab(canvas, body, self.tab, view,
                                   self._detail(view.inst.alias), palette,
                                   self.range_hours, self.sort, self.detail_scroll)
        if self.reveal is None:
            self._detail_total = total

    def _badges(self, palette) -> dict[int, tuple[str, Style]]:
        badges = {}
        data = self._detail(self.detail_alias) if self.detail_alias else DetailData()
        failed = data.tabs.get('failed')
        if failed is not None and (failed.lines or failed.error):
            badges[4] = ('●', Style(fg=palette['error']))
        journal = data.tabs.get('journal')
        if journal is not None and journal.lines:
            badges[5] = (str(len(journal.lines)), Style(fg=palette['error']))
        return badges

    # -- resize and theme -------------------------------------------------
    def on_resize(self, width: int, height: int) -> None:
        self.animator.finish_all()
        if self.header is not None:
            self.header.rect = Rect(0, 0, width, 1)
        if self.footer is not None:
            self.footer.rect = Rect(0, height - 1, width, 1)
        if self.mode == 'detail' and self.detail_alias is not None:
            layer = self._vm_layers.get(self.detail_alias)
            if layer is not None:
                layer.rect = self._detail_rect()
                layer.visible = True
                layer.z = 60
            for alias, other in self._vm_layers.items():
                if alias != self.detail_alias:
                    other.visible = False
            for title in self.title_layers.values():
                title.visible = False
        else:
            self._apply_layout(snap=True)
        if self.modal is not None:
            target = self._modal_rect()
            self.modal['target'] = target
            self.modal['start'] = Rect(target.x + target.w // 2 - 1, target.y + 3, 2, 1)
            self.modal['backdrop'].rect = Rect(0, 0, width, height)
            self.modal['layer'].rect = target
            self.modal['backdrop'].opacity = 0.45
        if self.help_layer is not None:
            w = min(52, max(20, width - 4))
            h = min(len(HELP_LINES) + 3, max(6, height - 2))
            self.help_layer.rect = Rect(max(0, (width - w) // 2),
                                        max(0, (height - h) // 2), w, h)
        if self.toast_layer is not None:
            self._place_toast()
        self.invalidate()
