"""The floating control bar: which controls exist for a file kind and host mode, and how they follow the session."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from . import host
from .controls import Capsule, Clock, ControlButton, PlayButton, Pill, SeekBar, VolumeSlider, unit

MAX_WIDTH_UNITS = 46             # the bar stops growing here, in controls units
COMPACT_UNITS = 26               # narrower than this, the volume slider and track buttons fold into "more"


def speed_text(speed):
    return f'{speed:g}×'


class ControlBar(Capsule):
    """Buttons are wired straight to the owning :class:`MediaPlayer`'s methods."""

    def __init__(self, player):
        super().__init__(player)
        self.player = player
        self.kind, self.mode, self.compact = 'video', 'embedded', False
        h = host.get()
        space = round(float(h.token('space_m')))
        column = QVBoxLayout(self)
        column.setContentsMargins(space, round(space * .75), space, round(space * .75))
        column.setSpacing(round(float(h.token('space_xs'))))

        self.elapsed, self.remaining = Clock(Qt.AlignLeft), Clock(Qt.AlignRight)
        self.seek = SeekBar()
        self.progress = QWidget()
        row = QHBoxLayout(self.progress)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(round(float(h.token('space_s'))))
        row.addWidget(self.elapsed)
        row.addWidget(self.seek, 1)
        row.addWidget(self.remaining)
        column.addWidget(self.progress)

        self.play = PlayButton('Reproducir · Espacio')
        self.back = ControlButton('replay_10', 'Retroceder 10 s · ←')
        self.ahead = ControlButton('forward_10', 'Avanzar 10 s · →')
        self.previous = ControlButton('skip_previous', 'Anterior · P')
        self.next = ControlButton('skip_next', 'Siguiente · N')
        self.mute = ControlButton('volume_up', 'Silenciar · M', scale=1.8)
        self.volume = VolumeSlider()
        self.volume.setFixedWidth(round(unit() * 5))
        self.speed = Pill('1×', 'Velocidad de reproducción')
        self.subtitles = ControlButton('closed_caption', 'Subtítulos · C', scale=1.8)
        self.audio = ControlButton('audiotrack', 'Pista de audio · A', scale=1.8)
        self.more = ControlButton('more_vert', 'Más opciones', scale=1.8)
        self.fullscreen = ControlButton('fullscreen', 'Pantalla completa · F', scale=1.8)
        self.expand = ControlButton('open_in_full', 'Abrir en Wysun Player', scale=1.8)
        self.zoom_out = ControlButton('zoom_out', 'Alejar · −', scale=1.8)
        self.zoom = Pill('100 %', 'Ajustar o tamaño real · doble clic')
        self.zoom_in = ControlButton('zoom_in', 'Acercar · +', scale=1.8)
        self.rotate = ControlButton('rotate_right', 'Girar · R', scale=1.8)
        self.animation = ControlButton('play_arrow', 'Reproducir animación · Espacio', scale=1.8)

        self.left, self.center, self.right = QWidget(), QWidget(), QWidget()
        for group, widgets in ((self.left, (self.mute, self.volume)),
                               (self.center, (self.previous, self.back, self.play, self.ahead, self.next, self.animation,
                                              self.zoom_out, self.zoom, self.zoom_in, self.rotate)),
                               (self.right, (self.speed, self.subtitles, self.audio, self.more, self.fullscreen, self.expand))):
            layout = QHBoxLayout(group)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(round(float(h.token('space_xs'))))
            for widget in widgets:
                layout.addWidget(widget, 0, Qt.AlignVCenter)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.left, 1, Qt.AlignLeft)
        buttons.addWidget(self.center, 0, Qt.AlignCenter)
        buttons.addWidget(self.right, 1, Qt.AlignRight)
        column.addLayout(buttons)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        play = player
        self.play.clicked.connect(play.toggle)
        self.back.clicked.connect(lambda: play.skip(-10))
        self.ahead.clicked.connect(lambda: play.skip(10))
        self.previous.clicked.connect(lambda: play.step_collection(-1))
        self.next.clicked.connect(lambda: play.step_collection(1))
        self.mute.clicked.connect(play.toggle_mute)
        self.volume.volumeChanged.connect(play.set_volume)
        self.seek.scrubbed.connect(play.session.scrub)
        self.seek.seekRequested.connect(play.session.seek)
        self.speed.clicked.connect(lambda: play.show_speed_menu(self.speed))
        self.subtitles.clicked.connect(lambda: play.show_subtitle_menu(self.subtitles))
        self.audio.clicked.connect(lambda: play.show_audio_menu(self.audio))
        self.more.clicked.connect(lambda: play.show_more_menu(self.more))
        self.fullscreen.clicked.connect(play.toggle_fullscreen)
        self.expand.clicked.connect(play.expandRequested.emit)
        self.zoom_out.clicked.connect(lambda: play.zoom(1 / 1.25))
        self.zoom_in.clicked.connect(lambda: play.zoom(1.25))
        self.zoom.clicked.connect(play.toggle_fit)
        self.rotate.clicked.connect(play.rotate)
        self.animation.clicked.connect(play.toggle)

    # -------------------------------------------------------------- layout
    def configure(self, kind, mode, count=1, width=0):
        """Show the controls that make sense for ``kind`` ('video', 'audio', 'image') in ``mode``."""
        self.kind, self.mode = kind, mode
        self.compact = bool(width) and width < unit() * COMPACT_UNITS
        timed = kind in ('video', 'audio')
        full = mode == 'full'
        self.progress.setVisible(timed)
        self.play.setVisible(timed)
        self.back.setVisible(timed and not self.compact)
        self.ahead.setVisible(timed and not self.compact)
        self.previous.setVisible(count > 1 and full)
        self.next.setVisible(count > 1 and full)
        self.animation.setVisible(False)
        for widget in (self.zoom_out, self.zoom, self.zoom_in, self.rotate):
            widget.setVisible(kind == 'image' and full)
        self.mute.setVisible(timed)
        self.volume.setVisible(timed and full and not self.compact)
        self.speed.setVisible(timed and full and not self.compact)
        self.subtitles.setVisible(kind == 'video' and full and not self.compact)
        self.audio.setVisible(timed and full and not self.compact and len(self.player.session.tracks('audio')) > 1)
        self.fullscreen.setVisible(full and kind != 'audio')
        self.expand.setVisible(not full)
        self.more.setVisible(True)
        self.updateGeometry()

    def preferred_height(self):
        return self.layout().sizeHint().height()

    def show_animation(self, available, running):
        """Play/pause for an animated image."""
        self.animation.setVisible(available and self.kind == 'image')
        self.animation.set_symbol('pause' if running else 'play_arrow')

    # ------------------------------------------------------------- session
    def sync_state(self, state):
        playing = state == 'playing'
        self.play.set_playing(playing)
        self.play.set_label(('Pausar' if playing else 'Reproducir') + ' · Espacio')

    def sync_progress(self, position, duration):
        self.seek.set_duration(duration)
        self.seek.set_position(position)
        self.elapsed.set_seconds(position)
        self.remaining.set_seconds(max(0.0, duration - position), remaining=True)

    def sync_volume(self, volume, muted):
        self.volume.set_volume(0 if muted else volume)
        self.mute.set_symbol('volume_off' if muted or volume <= 0 else 'volume_down' if volume < 50 else 'volume_up')
        self.mute.set_label(('Activar sonido' if muted else 'Silenciar') + ' · M')

    def sync_speed(self, speed):
        self.speed.setText(speed_text(speed))
        self.speed.highlight = abs(speed - 1) > .001
        self.speed.updateGeometry()
        self.speed.update()

    def sync_zoom(self, percent, fitted):
        self.zoom.setText(f'{percent:.0f} %')
        self.zoom.highlight = not fitted
        self.zoom.updateGeometry()
        self.zoom.update()

    def sync_fullscreen(self, active):
        self.fullscreen.set_symbol('fullscreen_exit' if active else 'fullscreen')
        self.fullscreen.set_label('Salir de pantalla completa · Esc' if active else 'Pantalla completa · F')
