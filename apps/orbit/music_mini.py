"""Small native quick player. Shares the full app's queue and mpv, never duplicates audio."""
import html
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QKeySequence,QShortcut
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QLineEdit,QListWidget,QListWidgetItem,QSlider
from desktop_common import Surface,button,text_label
from music_app_window import Cover,SeekSlider,control
from music_library import normalize
from music_keyboard import KeyboardNavigation, SongDelegate, shortcut, playback_shortcuts, keyboard_help
from music_window import stamp
from icons import icon
from theme_tokens import apply_style

class MiniPlayer(Surface):
    def __init__(self,player):
        super().__init__('Wysun Music',width=420,height=620)
        self.player=player;self.last_key=None;self.last_cover=None;self.rendered=None
        self.outer.setContentsMargins(24,20,24,20);self.outer.setSpacing(12)
        self.search=QLineEdit();self.search.setPlaceholderText('Cambiar de canción…');self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Buscar en toda la biblioteca');self.search.textChanged.connect(self.results);self.outer.addWidget(self.search)
        self.matches=QListWidget();self.matches.setMaximumHeight(176);self.matches.hide()
        self.matches.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.matches.setItemDelegate(SongDelegate(self.matches));self.matches.setMouseTracking(True)
        self.matches.setAccessibleName('Canciones disponibles');self.matches.itemClicked.connect(self.play_item);self.matches.itemActivated.connect(self.play_item)
        self.outer.addWidget(self.matches)
        cover_row=QHBoxLayout();cover_row.addStretch();self.cover=Cover('Wysun Music',200);cover_row.addWidget(self.cover);cover_row.addStretch();self.outer.addLayout(cover_row)
        self.title=text_label('Elige una canción');self.title.setAlignment(Qt.AlignCenter);apply_style(self.title,'font-size:19px;font-weight:600;');self.outer.addWidget(self.title)
        self.artist=text_label('');self.artist.setAlignment(Qt.AlignCenter);apply_style(self.artist,'font-size:12px;color:#A0ACC0;');self.outer.addWidget(self.artist)
        row=QHBoxLayout();row.addStretch();self.favorite=control('Favoritos',player.favorite_current,'heart',checkable=True);row.addWidget(self.favorite)
        self.previous=control('Anterior',lambda:player.advance(-1),'skip-back');row.addWidget(self.previous)
        self.play=control('Reproducir',player.toggle_play,'play',primary=True);self.play.setFixedSize(48,48);row.addWidget(self.play)
        self.next=control('Siguiente',lambda:player.advance(1),'skip-forward');row.addWidget(self.next)
        self.shuffle=control('Aleatorio',self.toggle_shuffle,'shuffle',checkable=True);row.addWidget(self.shuffle);row.addStretch();self.outer.addLayout(row)
        self.seek=SeekSlider();self.seek.setAccessibleName('Posición de reproducción');self.seek.seeked.connect(player.seek_to);self.outer.addWidget(self.seek)
        time_row=QHBoxLayout();self.elapsed=text_label('0:00','subtitle');time_row.addWidget(self.elapsed);time_row.addStretch();self.total=text_label('0:00','subtitle');time_row.addWidget(self.total);self.outer.addLayout(time_row)
        footer=QHBoxLayout();footer.addWidget(control('Letra',self.show_lyrics,'file-text'));footer.addWidget(button('Abrir Wysun Music',self.open_full,symbol='arrow-up-right'),1)
        self.volume=QSlider(Qt.Horizontal);self.volume.setRange(0,100);self.volume.setFixedWidth(65);self.volume.setAccessibleName('Volumen');self.volume.valueChanged.connect(player.volume.setValue);footer.addWidget(self.volume);self.outer.addLayout(footer)
        self.timer=QTimer(self);self.timer.timeout.connect(self.sync);self.timer.start(200)
        QShortcut(QKeySequence('Ctrl+F'),self).activated.connect(self.search.setFocus)
        QShortcut(QKeySequence('Ctrl+Space'),self).activated.connect(player.toggle_play)
        QShortcut(QKeySequence('Ctrl+Left'),self).activated.connect(lambda:player.advance(-1))
        QShortcut(QKeySequence('Ctrl+Right'),self).activated.connect(lambda:player.advance(1))
        self.keyboard=KeyboardNavigation(self,self.search,self.matches,self.play_item,mini=True)
        playback_shortcuts(self,player)
        shortcut(self,'Ctrl+Return',self.open_full)
        shortcut(self,'Ctrl+L',self.show_lyrics)
        shortcut(self,'F1',lambda:keyboard_help(self,mini=True))
        self.search.setToolTip('↑ / ↓ elegir · Enter reproducir · Esc limpiar · Ctrl+Enter abrir Wysun Music')
        self.sync()

    def present(self):
        super().present();self.sync();self.search.setFocus()

    def results(self):
        query=normalize(self.search.text());self.matches.clear();self.matches.setVisible(bool(query))
        if not query:return
        words=query.split()
        for key in self.player.all_keys():
            track=self.player.state['tracks'][key]
            if all(word in normalize(track['title']+' '+track['artist']) for word in words):
                item=QListWidgetItem(track['title']+'\n'+track['artist']);item.setData(Qt.UserRole,key);self.matches.addItem(item)
        self.matches.setFixedHeight(min(3,max(1,self.matches.count()))*58+6)
        if self.matches.count():self.matches.setCurrentRow(0)
        if not self.matches.count():
            item=QListWidgetItem('No hay canciones con ese nombre');item.setFlags(Qt.NoItemFlags);self.matches.addItem(item)

    def play_item(self,item):
        if not item or not item.data(Qt.UserRole):return
        key=item.data(Qt.UserRole)
        keys=[self.matches.item(i).data(Qt.UserRole) for i in range(self.matches.count()) if self.matches.item(i).data(Qt.UserRole)]
        self.player.order.start(keys or self.player.all_keys(),key,self.player.shuffle.isChecked())
        self.player.order.repeat=self.player.repeat.isChecked();self.player.queue=self.player.order.keys.copy()
        self.player.play_key(key,keep_queue=True);self.search.clear();self.sync()

    def toggle_shuffle(self):
        self.player.shuffle.setChecked(self.shuffle.isChecked());self.player.change_shuffle()

    def sync(self):
        if not self.isVisible() and self.last_key is not None:return
        player=self.player;track=player.state['tracks'].get(player.current_key,{})
        if player.current_key!=self.last_key:
            self.last_key=player.current_key;self.last_cover=None
            self.title.setText(track.get('title','Elige una canción'));self.artist.setText(track.get('artist',''))
            self.cover.title=track.get('title','Wysun Music');self.cover.image=__import__('PySide6.QtGui',fromlist=['QPixmap']).QPixmap();self.cover.update()
            from ui_motion import reveal_content
            reveal_content(self.cover,140)
        path=player.covers.get(player.current_key)
        if path and path!=self.last_cover:self.cover.set_image(path);self.last_cover=path
        self.seek.setRange(0,round(player.duration));self.seek.setEnabled(bool(player.current_key))
        if not self.seek.isSliderDown():self.seek.setValue(round(player.current_position))
        self.elapsed.setText(stamp(player.current_position));self.total.setText(stamp(player.duration))
        self.favorite.setEnabled(bool(player.current_key));self.favorite.setChecked(player.current_key in player.favorite_keys)
        self.previous.setEnabled(player.previous_button.isEnabled());self.next.setEnabled(player.next_button.isEnabled())
        self.play.setEnabled(bool(player.current_key or player.all_keys()))
        state=(player.paused,player.shuffle.isChecked())
        if state!=self.rendered:
            self.rendered=state;self.play.setIcon(icon('play' if player.paused else 'pause',20,'#162436'))
            self.play.setAccessibleName('Reproducir' if player.paused else 'Pausar');self.play.setToolTip(self.play.accessibleName())
            self.shuffle.setChecked(player.shuffle.isChecked())
        self.volume.blockSignals(True);self.volume.setValue(player.volume.value());self.volume.blockSignals(False)

    def open_full(self):
        self.close();self.player.present()

    def show_lyrics(self):
        self.open_full()
        self.player.focus_lyrics()
