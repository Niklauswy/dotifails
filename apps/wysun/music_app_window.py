"""Dedicated, lightweight Wysun music library and player.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Presentation: modules/dashboard/Media.qml, dashboard/media/Details.qml,
components/widgets/CoverArt.qml and modules/nexus/NavPane.qml at
507d66285e9d9fde9330adc64159cfdebb28c19a. Upstream has no per-file notices.
Native translation only; see THIRD_PARTY.md and LICENSES/GPL-3.0.txt.
"""
import bisect
import html
import json
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QSize, QTimer, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPen, QPixmap, QKeySequence, QShortcut, QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView,
    QSlider, QPlainTextEdit, QStackedWidget, QScrollArea, QMenu, QStyle, QStyleOptionSlider,
    QSizeGrip, QApplication, QLabel)
from desktop_common import button, text_label, ElidedLabel
from icons import icon
from theme_tokens import apply_style, color, tokens, font, on_theme_changed
from music_material import apply_music_style, metric
from music_window import MusicWindow, stamp, STATUS
from music_library import PlaybackOrder, MusicStore, normalize, artists, parse_lrc
from music_metadata import Metadata
import music_data as music
from music_keyboard import KeyboardNavigation, shortcut, playback_shortcuts, keyboard_help


class SeekSlider(QSlider):
    seeked = Signal(int)

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setMinimumHeight(28)
        self.setSingleStep(5)
        self.setPageStep(5)
        self.sliderReleased.connect(lambda: self.seeked.emit(self.value()))

    def at(self, event):
        option = QStyleOptionSlider();self.initStyleOption(option)
        groove = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        pos = round(event.position().x()-groove.x()-handle.width()/2)
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), pos,
                                              max(1, groove.width()-handle.width()), option.upsideDown)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setFocus();self.setSliderDown(True);self.setValue(self.at(event));event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self.setValue(self.at(event));event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSliderDown():
            self.setValue(self.at(event));self.setSliderDown(False);event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown):
            self.seeked.emit(self.value())


class Cover(QWidget):
    clicked = Signal()

    def __init__(self, title='', size=96):
        super().__init__()
        self.title, self.image, self.paths = title, QPixmap(), []
        self.setFixedSize(size, size)
        self.setToolTip(title)
        self.setAccessibleName(title)

    def set_image(self, path):
        self.image = QPixmap(str(path));self.update()

    def paintEvent(self, event):
        painter = QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        radius = min(tokens()["radius_l"], self.width()/8)
        clip = QPainterPath();clip.addRoundedRect(rect, radius, radius);painter.setClipPath(clip)
        painter.fillRect(rect, color('hover'))
        images = [self.image] if not self.image.isNull() else [QPixmap(p) for p in self.paths[:4]]
        images = [p for p in images if not p.isNull()]
        if 1<len(images)<4:images=(images*4)[:4]
        if images:
            for i, image in enumerate(images):
                target = rect if len(images) == 1 else QRectF((i%2)*self.width()/2, (i//2)*self.height()/2, self.width()/2, self.height()/2)
                scaled = image.scaled(target.size().toSize(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x, y = (scaled.width()-target.width())/2, (scaled.height()-target.height())/2
                painter.drawPixmap(target, scaled, QRectF(x, y, target.width(), target.height()))
        else:
            painter.setPen(color('accent'))
            cover_font = font(role='title', weight=600);cover_font.setFamily('Rubik');cover_font.setPixelSize(max(metric('font_body'), int(self.width()*.25)));painter.setFont(cover_font)
            initials = ''.join(word[0] for word in self.title.split()[:2]).upper() or '♪'
            painter.drawText(rect, Qt.AlignCenter, initials)
        painter.setClipping(False);painter.setPen(QPen(color('line'),tokens()['border']));painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius);painter.end()


def control(label, callback, symbol, primary=False, checkable=False):
    result = button('', callback, 'primary' if primary else '', symbol)
    size = metric('space_xl', 2 if primary else 1.75)
    result.setFixedSize(size, size)
    result.setToolTip(label);result.setAccessibleName(label);result.setCheckable(checkable)
    return result


class MusicAppWindow(MusicWindow):
    def __init__(self, test=False):
        self.store = MusicStore(music.DATA)
        reference_file = music.DATA/'reference-manifest.json'
        if reference_file.exists():
            try:self.store.import_references(json.loads(reference_file.read_text()))
            except (OSError, ValueError):pass
        self.order = PlaybackOrder()
        self.favorite_keys = self.store.favorites()
        self.visible_keys = []
        self.row_signature = None
        self.covers = {}
        self.cover_widgets = {}
        self.gallery_signature = None
        self.artist_photo = None
        self.lyric_key = None
        self.lyric_rows = []
        self.lyric_index = -1
        self.lyric_scroll_animation = None
        self.current_position = 0
        self.ended = False
        self.current_audio = None
        self.artist_name = None
        self.view = 'home'
        self.metadata = None
        self.restoring = False
        super().__init__(test=test)
        self.setWindowTitle('Wysun Music')
        self.resize(1180, 760)
        self.setMinimumSize(820, 600)

        self.setObjectName('musicApp')
        apply_music_style(self)
        on_theme_changed(self.refresh_presentation)
        self.refresh_presentation()
        self.metadata = Metadata(music.DATA, self)
        self.metadata.ready.connect(self.metadata_ready)
        if not test:
            self.request_collection_covers()
        preferences = self.store.get('session', {})
        self.volume.setValue(preferences.get('volume', 60))
        self.shuffle.setChecked(preferences.get('shuffle', False))
        self.repeat.setChecked(preferences.get('repeat', False))
        self.order.repeat = self.repeat.isChecked()
        if preferences.get('order'):
            self.order.restore(preferences['order']);self.queue = self.order.keys.copy()
        key = preferences.get('track')
        if key and self.available(key):
            self.current_key = key
            self.current_position = preferences.get('position', 0)
            self.ended = preferences.get('ended',False)
            self.current_audio=self.playable(key)
            self.duration=self.current_audio.get('duration',0)
            self.seek.setRange(0,round(self.duration));self.seek.setValue(round(self.current_position));self.seek.setEnabled(True)
            self.total.setText(stamp(self.duration));self.elapsed.setText(stamp(self.current_position))
            self.show_current()
            self.status.setText('Lista para continuar · pulsa reproducir')
        self.go(preferences.get('view', 'home'), preferences.get('collection', 'all'), preferences.get('artist'))
        self.save_timer = QTimer(self);self.save_timer.timeout.connect(self.save_session)
        if not test:self.save_timer.start(5000)

    def build(self):
        # Compact native header: preserve shared Orbita window/close behavior.
        header = self.outer.itemAt(0)
        title_layout = header.itemAt(0).layout()
        title_layout.itemAt(1).widget().setText('Wysun Music')
        if title_layout.count() > 2:
            title_layout.itemAt(2).widget().hide()
        self.search = QLineEdit();self.search.setPlaceholderText('Buscar en toda tu música…')
        self.search.setAccessibleName('Buscar en toda la biblioteca');self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(180);self.search.setMaximumWidth(420)
        self.search.textChanged.connect(self.search_changed)
        header.insertWidget(1, self.search, 1)
        header.insertWidget(2, control('Añadir archivos', self.import_files, 'folder-open'))
        header.insertWidget(3, control('Buscar y descargar', lambda: self.go('online'), 'download'))
        body = QHBoxLayout();self.body_layout=body;body.setSpacing(metric('space_m'))
        sidebar = QWidget();self.sidebar=sidebar;sidebar.setObjectName('musicNavigation');side = QVBoxLayout(sidebar);side.setContentsMargins(*([metric('space_s')]*4));side.setSpacing(metric('space_m'))
        sidebar.setFixedWidth(metric('space_xl',7))
        self.nav = QListWidget();self.nav.setFixedHeight(metric('space_xl',10));self.nav.setSpacing(0);self.nav.setAccessibleName('Navegación de música')
        for key, name, symbol in [('home','Canciones','music'), ('albums','Álbumes','music'), ('favorites','Favoritos','heart'), ('artists','Artistas','users'), ('downloads','Descargas','download')]:
            item = QListWidgetItem(icon(symbol), name);item.setData(Qt.UserRole,key);item.setSizeHint(QSize(0,metric('space_xl',1.75)));self.nav.addItem(item)
        self.nav.currentItemChanged.connect(lambda item,_: self.go(item.data(Qt.UserRole)) if item else None)
        side.addWidget(self.nav)
        side.addWidget(text_label('Tus playlists', 'musicCategory'))
        self.collections = QListWidget();self.collections.setWordWrap(True);self.collections.setSpacing(metric('space_xs'))
        self.collections.setIconSize(QSize(30,30));self.collections.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.collections.currentItemChanged.connect(self.select_collection)
        side.addWidget(self.collections,1)
        side.addWidget(button('Carpeta de música', lambda: QDesktopServices.openUrl(__import__('PySide6.QtCore',fromlist=['QUrl']).QUrl.fromLocalFile(str(music.LIBRARY))), symbol='folder-open'))
        body.addWidget(sidebar)
        center = QWidget();self.center=center;content = QHBoxLayout(center);self.content_layout=content;content.setContentsMargins(0,0,0,0);content.setSpacing(metric('space_m'))
        self.hero = QWidget();self.hero.setObjectName('musicArtwork')
        hero = QVBoxLayout(self.hero);hero.setContentsMargins(*([metric('space_l')]*4));hero.setSpacing(metric('space_m'))
        self.category = text_label('Biblioteca local','musicCategory');hero.addWidget(self.category)
        self.hero_cover = Cover('Tu música',metric('space_xl',10));hero.addWidget(self.hero_cover,0,Qt.AlignHCenter)
        self.heading = text_label('Tu música','musicHeading');hero.addWidget(self.heading)
        self.summary = text_label('', 'subtitle');hero.addWidget(self.summary)
        self.source = QLabel();self.source.setWordWrap(True);self.source.setTextFormat(Qt.RichText);self.source.setOpenExternalLinks(False);self.source.linkActivated.connect(self.search_link)
        self.source.setObjectName('musicDetail');hero.addWidget(self.source)
        self.hero_play = button('Reproducir', self.play_view,'primary','play');hero.addWidget(self.hero_play)
        self.hero_shuffle = button('Aleatorio',self.shuffle_view,symbol='shuffle');hero.addWidget(self.hero_shuffle)
        hero.addStretch();content.addWidget(self.hero)
        self.pages = QStackedWidget();content.addWidget(self.pages,1)
        self.tree = QTreeWidget();self.tree.setColumnCount(5);self.tree.setHeaderLabels(['','Canción','Artista','Duración','♡'])
        self.tree.setRootIsDecorated(False);self.tree.setUniformRowHeights(True);self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setAccessibleName('Canciones disponibles');self.tree.setMouseTracking(True)
        self.tree.header().setSectionResizeMode(1,QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2,QHeaderView.Stretch)
        for col,width in [(0,30),(3,76),(4,42)]:self.tree.setColumnWidth(col,width)
        self.tree.setColumnWidth(2,200);self.tree.header().setMinimumSectionSize(28)
        self.tree.itemDoubleClicked.connect(self.row_double_clicked)
        self.tree.itemClicked.connect(self.row_clicked)
        self.tree.itemSelectionChanged.connect(self.update_actions)
        self.pages.addWidget(self.tree) # 0
        downloads = QWidget();dl = QVBoxLayout(downloads);dl.setContentsMargins(0,0,0,0)
        self.download_status = text_label('','subtitle');dl.addWidget(self.download_status)
        actions = QHBoxLayout();self.resume_button=button('Continuar',self.resume_downloads,'primary','download');actions.addWidget(self.resume_button)
        self.pause_downloads_button=button('Pausar cola',self.pause_downloads);actions.addWidget(self.pause_downloads_button)
        actions.addWidget(button('Reintentar errores',self.retry_downloads));actions.addStretch();dl.addLayout(actions)
        self.download_list = QListWidget();dl.addWidget(self.download_list,1)
        self.details = button('Mostrar detalles',self.toggle_details);dl.addWidget(self.details)
        self.download_log=QPlainTextEdit();self.download_log.setReadOnly(True);self.download_log.hide();dl.addWidget(self.download_log,1)
        self.pages.addWidget(downloads) # 1
        online = QWidget();ol=QVBoxLayout(online);ol.setContentsMargins(0,0,0,0)
        row=QHBoxLayout();self.online_query=QLineEdit();self.online_query.setPlaceholderText('Canción, YouTube o playlist de Spotify');self.online_query.returnPressed.connect(self.search_online)
        row.addWidget(self.online_query,1);self.online_button=button('Buscar',self.search_online,'primary','search');row.addWidget(self.online_button);ol.addLayout(row)
        self.online_results=QListWidget();self.online_results.setSelectionMode(QAbstractItemView.ExtendedSelection);ol.addWidget(self.online_results,1)
        self.online_results.itemDoubleClicked.connect(lambda _:self.enqueue_results())
        self.online_status=text_label('Elige las canciones que quieres guardar.','subtitle');ol.addWidget(self.online_status)
        ol.addWidget(button('Descargar selección',self.enqueue_results,'primary','download'));self.pages.addWidget(online) # 2
        self.gallery_scroll=QScrollArea();self.gallery_scroll.setWidgetResizable(True)
        self.gallery=QWidget();self.gallery_layout=QVBoxLayout(self.gallery);self.gallery_layout.setContentsMargins(0,0,4,0);self.gallery_layout.setSpacing(16)
        self.gallery_scroll.setWidget(self.gallery);self.pages.addWidget(self.gallery_scroll) # 3
        self.artist_list=QListWidget();self.artist_list.setSpacing(3);self.artist_list.setAccessibleName('Artistas de tu biblioteca')
        self.artist_list.itemClicked.connect(lambda item:self.go('artist', artist=item.data(Qt.UserRole)))
        self.artist_list.itemActivated.connect(lambda item:self.go('artist', artist=item.data(Qt.UserRole)))
        self.pages.addWidget(self.artist_list) # 4
        self.empty_label=text_label('','subtitle');self.empty_label.setAlignment(Qt.AlignCenter);self.pages.addWidget(self.empty_label) # 5
        body.addWidget(center,1)
        self.lyrics_panel=QWidget();self.lyrics_panel.setObjectName('musicLyrics');self.lyrics_panel.setFixedWidth(metric('space_xl', 13));lyrics=QVBoxLayout(self.lyrics_panel);lyrics.setContentsMargins(*([metric('space_m')]*4))
        lyric_header=QHBoxLayout();lyric_header.addWidget(text_label('LETRA','eyebrow'),1);lyric_header.addWidget(control('Cerrar letra',self.toggle_lyrics,'x'));lyrics.addLayout(lyric_header);self.lyric_title=text_label('Elige una canción','previewTitle');lyrics.addWidget(self.lyric_title)
        self.lyric_status=text_label('','subtitle');lyrics.addWidget(self.lyric_status)
        self.audio_version_button=button('Usar audio de canción',lambda:self.play_key(self.current_key,keep_queue=True),symbol='music');self.audio_version_button.hide();lyrics.addWidget(self.audio_version_button)
        self.lyric_list=QListWidget();self.lyric_list.setWordWrap(True);self.lyric_list.setSpacing(6);self.lyric_list.setSelectionMode(QAbstractItemView.SingleSelection)
        apply_style(self.lyric_list,'QListWidget::item{padding:@space_s @space_xs;color:@subtle;border-radius:@radius_s;}QListWidget::item:selected{background:@row_hover;color:@text;}QListWidget::item:hover{background:@card;}')
        self.lyric_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.lyric_list.setTextElideMode(Qt.ElideNone)
        self.lyric_list.setToolTip('Clic en una línea para ir a ese momento de la canción')
        self.lyric_list.itemClicked.connect(self.seek_lyric);self.lyric_list.itemActivated.connect(self.seek_lyric);lyrics.addWidget(self.lyric_list,1)
        offsets=QHBoxLayout();offsets.addWidget(button('− 0.5 s',lambda:self.offset_lyrics(-.5)))
        self.offset_label=text_label('0.0 s','subtitle');offsets.addWidget(self.offset_label);offsets.addWidget(button('+ 0.5 s',lambda:self.offset_lyrics(.5)));lyrics.addLayout(offsets)
        self.lyrics_panel.hide();body.addWidget(self.lyrics_panel);self.outer.addLayout(body,1)
        player=QWidget();self.player_panel=player;player.setObjectName('musicPlayer')
        apply_style(player,'QWidget#musicPlayer{background:@surface;border-radius:@radius_l;}')
        pl=QVBoxLayout(player);pl.setContentsMargins(*([metric('space_m')]*4));pl.setSpacing(metric('space_xs'))
        row=QHBoxLayout();row.setSpacing(metric('space_s'));self.now_cover=Cover('Música',metric('space_xl',2));row.addWidget(self.now_cover)
        now=QVBoxLayout();now.setSpacing(metric('space_xs'));self.now_title=ElidedLabel('Elige una canción');self.now_title.setObjectName('musicTrackTitle');now.addWidget(self.now_title)
        self.now_artist=QLabel('Tu biblioteca local');self.now_artist.setMinimumWidth(0);
        from PySide6.QtWidgets import QSizePolicy
        self.now_artist.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);self.now_artist.setTextFormat(Qt.RichText);self.now_artist.linkActivated.connect(lambda name:self.go('artist',artist=name))
        self.now_artist.setObjectName('musicDetail');now.addWidget(self.now_artist);row.addLayout(now,1)
        self.favorite_button=control('Añadir a favoritos',self.favorite_current,'heart',checkable=True);row.addWidget(self.favorite_button)
        self.shuffle=control('Aleatorio',self.change_shuffle,'shuffle',checkable=True);row.addWidget(self.shuffle)
        self.previous_button=control('Anterior · Ctrl+←',lambda:self.advance(-1),'skip-back');row.addWidget(self.previous_button)
        self.play_button=control('Reproducir · Ctrl+Espacio',self.toggle_play,'play',primary=True);row.addWidget(self.play_button)
        self.next_button=control('Siguiente · Ctrl+→',lambda:self.advance(1),'skip-forward');row.addWidget(self.next_button)
        self.repeat=control('Repetir lista',self.change_repeat,'repeat',checkable=True);row.addWidget(self.repeat)
        row.addSpacing(10);row.addWidget(control('Letra sincronizada',self.toggle_lyrics,'file-text'))
        row.addWidget(control('Silenciar',self.mute,'volume-2'));self.volume=QSlider(Qt.Horizontal);self.volume.setFixedWidth(metric('space_xl',3));self.volume.setRange(0,100);self.volume.setValue(60)
        self.volume.setAccessibleName('Volumen');self.volume.valueChanged.connect(lambda value:self.command(['set_property','volume',value]));row.addWidget(self.volume)
        pl.addLayout(row)
        timeline=QHBoxLayout();self.elapsed=text_label('0:00','subtitle');self.elapsed.setFixedWidth(40);timeline.addWidget(self.elapsed)
        self.seek=SeekSlider();self.seek.setAccessibleName('Posición de reproducción');self.seek.setEnabled(False);self.seek.seeked.connect(self.seek_to)
        timeline.addWidget(self.seek,1);self.total=text_label('0:00','subtitle');self.total.setFixedWidth(40);timeline.addWidget(self.total);pl.addLayout(timeline)
        self.outer.addWidget(player)
        footer=QHBoxLayout();self.status=text_label('Reproducción local · puedes cerrar el panel y seguir escuchando','subtitle');footer.addWidget(self.status,1)
        footer.addWidget(QSizeGrip(self));self.outer.addLayout(footer)
        # Compatibility for the older downloader helpers.
        self.download_button=self.details
        QShortcut(QKeySequence('Ctrl+F'),self).activated.connect(self.search.setFocus)
        QShortcut(QKeySequence('Ctrl+Space'),self).activated.connect(self.toggle_play)
        QShortcut(QKeySequence('Ctrl+Right'),self).activated.connect(lambda:self.advance(1))
        QShortcut(QKeySequence('Ctrl+Left'),self).activated.connect(lambda:self.advance(-1))
        shortcut(self.tree,'Return',self.play_selection,Qt.WidgetShortcut)
        shortcut(self.tree,'Enter',self.play_selection,Qt.WidgetShortcut)
        shortcut(self.tree,'F',self.favorite_selected,Qt.WidgetShortcut)
        shortcut(self.tree,'Ctrl+Return',self.open_selected_artist,Qt.WidgetShortcut)
        QShortcut(QKeySequence('Ctrl+L'),self).activated.connect(self.focus_lyrics)
        self.keyboard=KeyboardNavigation(self,self.search,self.tree,self.play_selection)
        playback_shortcuts(self,self)
        shortcut(self,'Ctrl+O',self.import_files)
        shortcut(self.online_results,'Ctrl+Return',self.enqueue_results,Qt.WidgetShortcut)
        for number,view in enumerate(('home','favorites','artists','downloads','online'),1):
            shortcut(self,'Alt+'+str(number),lambda view=view:self.keyboard_page(view))
        shortcut(self,'Ctrl+J',self.focus_content)
        shortcut(self,'F1',lambda:keyboard_help(self))
        self.collections.itemActivated.connect(lambda _:self.focus_content())
        self.nav.itemActivated.connect(lambda _:self.focus_content())
        self.source.setTextInteractionFlags(Qt.TextBrowserInteraction);self.source.setFocusPolicy(Qt.StrongFocus)
        self.now_artist.setTextInteractionFlags(Qt.TextBrowserInteraction);self.now_artist.setFocusPolicy(Qt.StrongFocus)
        self.search.setToolTip('↑ / ↓ elegir · Enter reproducir · Esc limpiar · Ctrl+J ir a resultados')

    def refresh_presentation(self):
        """Reflow native metrics and cached brushes after a live scheme change."""
        self.outer.setContentsMargins(*([metric('space_l')]*4))
        self.outer.setSpacing(metric('space_m'))
        self.sidebar.setFixedWidth(metric('space_xl',7))
        self.hero.setFixedWidth(metric('space_xl',11))
        self.hero_cover.setFixedSize(*([metric('space_xl', 11)-metric('space_l',2)]*2))
        for layout in (self.body_layout,self.content_layout):layout.setSpacing(metric('space_m'))
        self.row_signature=None
        self.render_tracks()
        for i in range(self.lyric_list.count()):
            self.lyric_list.item(i).setForeground(color('accent' if i==self.lyric_index else 'subtle'))
            self.size_lyric(self.lyric_list.item(i))
        self.update()

    def focus_content(self):
        page=self.pages.currentWidget()
        if page in (self.tree,self.artist_list):page.setFocus();return
        candidates=page.findChildren(QWidget)
        target=next((widget for widget in candidates if widget.isVisible() and widget.isEnabled() and widget.focusPolicy() & Qt.TabFocus),page)
        target.setFocus()

    def keyboard_page(self,view):
        self.go(view)
        target={'artists':self.artist_list,'downloads':self.download_list,'online':self.online_query,'favorites':self.tree,'home':self.tree}[view]
        target.setFocus()

    def open_selected_artist(self):
        item=self.tree.currentItem()
        if item:
            track=self.state['tracks'].get(item.data(0,Qt.UserRole),{})
            names=artists(track)
            if names:self.go('artist',artist=names[0]);self.tree.setFocus()

    def focus_lyrics(self):
        if not self.lyrics_panel.isVisible():self.toggle_lyrics()
        self.lyric_list.setFocus()

    def available(self,key):
        track=self.state['tracks'].get(key,{})
        return track.get('status')=='ready' and bool(track.get('path')) and Path(track['path']).is_file()

    def playable(self,key):
        preferred=self.store.preferred(key)
        variant=self.state['tracks'].get('album-audio-'+key,{})
        reference=self.store.reference(key)
        if variant.get('status')=='ready' and abs(variant.get('duration',0)-(reference.get('duration') or 0))<=2:
            preferred='album-audio-'+key
        return self.state['tracks'][preferred] if self.available(preferred) else self.state['tracks'].get(key,{})

    def all_keys(self):
        return [k for k,t in self.state['tracks'].items() if not t.get('album_audio_of') and self.available(k)]

    def selected_keys(self):
        if self.view=='favorites':return [k for k in self.all_keys() if k in self.favorite_keys]
        if self.view=='artist':return [k for k in self.all_keys() if normalize(self.artist_name) in [normalize(a) for a in artists(self.state['tracks'][k])]]
        if self.collection!='all':return [k for k in self.state['collections'].get(self.collection,{}).get('tracks',[]) if self.available(k) and not self.state['tracks'][k].get('album_audio_of')]
        return self.all_keys()

    def refresh(self,force=False):
        try:mtime=(music.DATA/'library.json').stat().st_mtime_ns
        except FileNotFoundError:mtime=0
        if not force and mtime==self.last_mtime:return
        try:self.state=music.read_state()
        except (OSError,ValueError) as error:self.status.setText('No se pudo leer la biblioteca: '+str(error));return
        self.last_mtime=mtime
        self.collections.blockSignals(True);self.collections.clear()
        for key,c in self.state['collections'].items():
            if key=='audio-versions':continue
            title={'nadie-sabe':'Nadie sabe…','bad-bunny':'Bad Bunny · éxitos','top-global':'Top 100 · Global','top-mexico':'Top 100 · México'}.get(key,c['title'])
            item=QListWidgetItem(title);item.setData(Qt.UserRole,key);item.setToolTip(c['title']);item.setSizeHint(QSize(0,metric('space_xl',2)));self.collections.addItem(item)
            if key==self.collection:self.collections.setCurrentItem(item)
        self.collections.blockSignals(False)
        self.render_downloads();self.render_tracks()
        if self.view=='albums':self.render_gallery()
        if self.view=='artists':self.render_artists()
        self.update_collection_icons()

    def go(self,view='home',collection='all',artist=None):
        if view not in {'home','albums','tracks','favorites','artists','artist','downloads','online'}:view='home'
        self.view,self.collection,self.artist_name=view,collection,artist
        self.search.blockSignals(True);self.search.clear();self.search.blockSignals(False)
        self.nav.blockSignals(True);self.nav.clearSelection()
        for i in range(self.nav.count()):
            if self.nav.item(i).data(Qt.UserRole)==view:self.nav.setCurrentRow(i)
        self.nav.blockSignals(False)
        self.collections.blockSignals(True);self.collections.clearSelection()
        for i in range(self.collections.count()):
            if self.collections.item(i).data(Qt.UserRole)==collection:self.collections.setCurrentRow(i)
        self.collections.blockSignals(False)
        self.hero_cover.image=QPixmap();self.hero_cover.paths=[];self.hero_cover.title=artist or 'Música';self.hero_cover.update()
        self.source.clear();self.hero_play.show();self.hero_shuffle.show()
        if view=='albums':
            self.category.setText('BIBLIOTECA LOCAL');self.heading.setText('Álbumes y playlists')
            self.summary.setText(f'{len(self.all_keys())} canciones · guardadas en este equipo');self.hero_cover.show();self.render_gallery();self.pages.setCurrentIndex(3)
        elif view=='artists':
            self.category.setText('TU BIBLIOTECA');self.heading.setText('Artistas');self.hero_cover.show();self.hero_play.hide();self.hero_shuffle.hide();self.render_artists();self.pages.setCurrentIndex(4)
        elif view in {'downloads','online'}:
            self.category.setText('TU BIBLIOTECA');self.heading.setText('Descargas' if view=='downloads' else 'Añadir música')
            self.summary.setText('Gestiona lo que guardas en este equipo');self.hero_cover.show();self.hero_play.hide();self.hero_shuffle.hide();self.pages.setCurrentIndex(1 if view=='downloads' else 2)
        else:
            self.hero_cover.show();self.category.setText('ARTISTA' if view=='artist' else ('FAVORITOS' if view=='favorites' else 'BIBLIOTECA LOCAL' if view=='home' else 'PLAYLIST'))
            c=self.state['collections'].get(collection,{})
            self.heading.setText(artist if view=='artist' else ('Tus favoritos' if view=='favorites' else c.get('title','Todas las canciones')))
            if c.get('date'):self.category.setText('RANKING · '+c['date'])
            self.hero_cover.title=self.heading.text();self.apply_cover(collection,self.hero_cover)
            if view=='artist':
                album_links=['<a href="collection:'+html.escape(k,quote=True)+'">'+html.escape(c['title'])+'</a>' for k,c in self.state['collections'].items() if '/album/' in c.get('source','') and any(normalize(artist) in [normalize(a) for a in artists(self.state['tracks'].get(t,{}))] for t in c['tracks'])]
                self.source.setOpenExternalLinks(False);self.source.setText(' · '.join(album_links))
                if self.metadata and not self.test:self.metadata.artist(artist)
            self.render_tracks();self.pages.setCurrentIndex(0 if self.visible_keys else 5)
        self.update_actions()
        from ui_motion import reveal_content
        reveal_content(self.pages.currentWidget(),metric('motion_fast'))

    def select_collection(self,item,previous=None):
        if item:self.go('tracks',item.data(Qt.UserRole))

    def search_changed(self):
        query=normalize(self.search.text())
        if query:
            self.hero_cover.show();self.category.setText('BÚSQUEDA GLOBAL');self.heading.setText('Resultados en toda tu música')
            self.render_tracks();self.pages.setCurrentIndex(0 if self.visible_keys else 5)
            matching_artists=sorted({a for k in self.visible_keys for a in artists(self.state['tracks'][k]) if query in normalize(a)})
            matching_collections=[(k,c) for k,c in self.state['collections'].items() if k!='audio-versions' and query in normalize(c['title'])]
            links=['<a href="artist:'+html.escape(a,quote=True)+'">'+html.escape(a)+'</a>' for a in matching_artists[:5]]
            links+=['<a href="collection:'+html.escape(k,quote=True)+'">'+html.escape(c['title'])+'</a>' for k,c in matching_collections[:3]]
            self.source.setOpenExternalLinks(False);self.source.setText(' · '.join(links))
        else:self.go(self.view,self.collection,self.artist_name)

    def search_link(self,route):
        if route.startswith('https://'):
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(route));return
        kind,name=route.split(':',1)
        if kind=='artist':self.go('artist',artist=name)
        else:self.go('tracks',name)

    def render_tracks(self):
        query=normalize(self.search.text())
        keys=self.all_keys() if query else self.selected_keys()
        if query:
            words=query.split()
            keys=[k for k in keys if all(word in normalize(self.state['tracks'][k]['title']+' '+self.state['tracks'][k]['artist']) for word in words)]
        self.visible_keys=keys
        signature=[(k,self.state['tracks'][k]['title'],self.state['tracks'][k]['artist'],round(self.playable(k).get('duration',0)),k in self.favorite_keys,k==self.current_key) for k in keys]
        if signature!=self.row_signature:
            selected=self.tree.currentItem();selected=selected.data(0,Qt.UserRole) if selected else None
            scroll=self.tree.verticalScrollBar().value()
            self.tree.blockSignals(True)
            # Reuse items when the row order did not change: download progress must not reset the table.
            existing=[self.tree.topLevelItem(i).data(0,Qt.UserRole) for i in range(self.tree.topLevelItemCount())]
            if existing!=keys:self.tree.clear()
            for i,(key,title,artist,duration,favorite,current) in enumerate(signature):
                item=self.tree.topLevelItem(i)
                if item is None:item=QTreeWidgetItem();self.tree.addTopLevelItem(item)
                for col,value in enumerate(['▶' if current else str(i+1),title,artist,stamp(duration),'♥' if favorite else '♡']):item.setText(col,value)
                item.setData(0,Qt.UserRole,key);item.setSizeHint(0,QSize(0,metric('space_xl',2)))
                item.setToolTip(1,title);item.setToolTip(2,'Ver artista · '+artist);item.setToolTip(4,'Quitar de favoritos' if favorite else 'Añadir a favoritos · F')
                item.setTextAlignment(3,Qt.AlignRight|Qt.AlignVCenter);item.setTextAlignment(4,Qt.AlignCenter)
                item.setForeground(0,color('accent' if current else 'subtle'));item.setForeground(4,color('accent' if favorite else 'subtle'))
                if key==selected:self.tree.setCurrentItem(item)
            self.tree.blockSignals(False);self.tree.verticalScrollBar().setValue(scroll);self.row_signature=signature
        self.summary.setText(f'{len(keys)} canciones · {stamp(sum(self.playable(k).get("duration",0) for k in keys))} de música')
        self.empty_label.setText('No hay resultados para esta búsqueda.' if query else ('Dale un corazón a una canción para guardarla aquí.' if self.view=='favorites' else 'Todavía no hay canciones disponibles.'))
        self.update_actions()

    def row_clicked(self,item,column):
        key=item.data(0,Qt.UserRole)
        if column==4:self.favorite(key)
        elif column==2:
            names=artists(self.state['tracks'][key])
            if len(names)==1:self.go('artist',artist=names[0])
            else:
                menu=QMenu(self);apply_style(menu,'QMenu{background:@menu;color:@text;padding:6px;border:@border solid @line_strong;}QMenu::item{padding:10px 20px;}QMenu::item:selected{background:@menu_selected;}')
                for name in names:menu.addAction(name,lambda checked=False,n=name:self.go('artist',artist=n))
                menu.exec(self.tree.viewport().mapToGlobal(self.tree.visualItemRect(item).center()))

    def row_double_clicked(self,item,column):
        if column not in (2,4):self.play_key(item.data(0,Qt.UserRole))

    def favorite(self,key):
        self.store.toggle(key);self.favorite_keys=self.store.favorites();self.render_tracks()
        self.favorite_button.setChecked(self.current_key in self.favorite_keys)
        self.favorite_button.setToolTip('Quitar de favoritos' if self.current_key in self.favorite_keys else 'Añadir a favoritos')
        if self.view=='favorites':self.pages.setCurrentIndex(0 if self.visible_keys else 5)

    def favorite_current(self):
        if self.current_key:self.favorite(self.current_key)

    def favorite_selected(self):
        item=self.tree.currentItem()
        if item:self.favorite(item.data(0,Qt.UserRole))

    def render_gallery(self):
        signature=[(k,c['title'],c.get('date'),tuple(t for t in c['tracks'] if self.available(t))) for k,c in self.state['collections'].items() if k!='audio-versions']
        if signature==self.gallery_signature:return
        self.gallery_signature=signature
        self.cover_widgets={}
        while self.gallery_layout.count():
            widget=self.gallery_layout.takeAt(0).widget()
            if widget:widget.hide();widget.deleteLater()
        groups=[('Álbumes',lambda c:'/album/' in c.get('source','')),('Selecciones',lambda c:not c.get('date') and '/album/' not in c.get('source','')),('Rankings',lambda c:bool(c.get('date')))]
        for label,predicate in groups:
            collections=[(k,c) for k,c in self.state['collections'].items() if k!='audio-versions' and predicate(c)]
            if not collections:continue
            section=QWidget();layout=QVBoxLayout(section);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
            layout.addWidget(text_label(label,'previewTitle'));grid=QGridLayout();grid.setSpacing(12)
            for i,(key,c) in enumerate(collections):
                card=QWidget();card.setMinimumHeight(metric('space_xl',5));card.setObjectName('collectionCard');apply_style(card,'QWidget#collectionCard{background:@fill;border-radius:@radius_l;}')
                cl=QHBoxLayout(card);cl.setContentsMargins(*([metric('space_m')]*4));cl.setSpacing(metric('space_m'))
                cover=Cover(c['title'],metric('space_xl',3));cl.addWidget(cover);self.cover_widgets[key]=cover;self.apply_cover(key,cover)
                info=QVBoxLayout();info.setSpacing(6);title=text_label(c['title']);apply_style(title,'font-size:@font_heading;font-weight:600;');info.addWidget(title)
                count=sum(self.available(k) for k in c['tracks']);info.addWidget(text_label(f'{count} canciones'+(' · '+c['date'] if c.get('date') else ''),'subtitle'))
                action=button('Abrir playlist',lambda k=key:self.go('tracks',k),symbol='arrow-right');info.addWidget(action);cl.addLayout(info,1)
                grid.addWidget(card,i,0)
            layout.addLayout(grid);self.gallery_layout.addWidget(section)
        self.gallery_layout.addWidget(button('Ver todas las canciones',lambda:self.go('tracks'),symbol='music'))
        spacer=QWidget();spacer.setFixedHeight(1);self.gallery_layout.addWidget(spacer);self.gallery_layout.addStretch()

    def render_artists(self):
        counts={}
        for key in self.all_keys():
            for artist in artists(self.state['tracks'][key]):counts[artist]=counts.get(artist,0)+1
        self.artist_list.clear()
        for artist,count in sorted(counts.items(),key=lambda v:normalize(v[0])):
            item=QListWidgetItem(artist+'\n'+str(count)+' canciones');item.setData(Qt.UserRole,artist);item.setSizeHint(QSize(0,62));self.artist_list.addItem(item)
        self.summary.setText(f'{len(counts)} artistas · incluye colaboraciones')

    def request_collection_covers(self):
        if not self.metadata:return
        for key,c in self.state['collections'].items():
            if c.get('cover_url'):
                self.metadata.request('cover',key,lambda c=c:dict(path=self.metadata.download_image(c['cover_url']),source=c['source']))
            elif '/album/' in c.get('source',''):self.metadata.cover(key,c['source'])
            # Playlist mosaics use four actual album covers, avoiding video thumbnails.
            elif key!='audio-versions':
                for track_key in c['tracks'][:4]:self.request_track_cover(track_key)

    def request_track_cover(self,key):
        if not self.metadata or self.test:return
        reference=self.store.reference(key)
        if reference.get('spotify') or (len(key)==22 and key.isalnum()):self.metadata.cover(key,reference.get('spotify') or 'https://open.spotify.com/track/'+key)

    def apply_cover(self,key,widget):
        if key in self.covers:widget.set_image(self.covers[key]);return
        c=self.state['collections'].get(key,{})
        widget.paths=[self.covers[k] for k in c.get('tracks',[]) if k in self.covers][:4];widget.update()

    def update_collection_icons(self):
        for i in range(self.collections.count()):
            item=self.collections.item(i);key=item.data(Qt.UserRole)
            path=self.covers.get(key)
            if not path:
                path=next((self.covers[k] for k in self.state['collections'][key]['tracks'] if k in self.covers),None)
            if path:item.setIcon(__import__('PySide6.QtGui',fromlist=['QIcon']).QIcon(path))

    def metadata_ready(self,kind,key,data):
        if kind=='cover' and data.get('path'):
            self.covers[key]=data['path']
            if key in self.cover_widgets:self.apply_cover(key,self.cover_widgets[key])
            for collection,widget in self.cover_widgets.items():self.apply_cover(collection,widget)
            if self.view in {'home','tracks','favorites'}:self.apply_cover(self.collection,self.hero_cover)
            if key==self.current_key:self.now_cover.set_image(data['path'])
            self.update_collection_icons()
        elif kind=='artist' and self.view=='artist' and key==self.artist_name:
            if data.get('path'):
                self.hero_cover.set_image(data['path'])
                source=html.escape(data.get('source',''),quote=True);license=html.escape(data.get('license',''))
                self.source.setOpenExternalLinks(False);self.source.setText(self.source.text()+f' · <a href="{source}">Foto y créditos · {license}</a>')
        elif kind=='lyrics' and key==self.lyric_key:self.show_lyrics(data)
        elif kind=='spotify-import':self.spotify_import_ready(data)

    def show_current(self):
        track=self.state['tracks'].get(self.current_key,{})
        self.now_title.setText(track.get('title','Elige una canción'))
        links=['<a style="color:inherit;text-decoration:none" href="'+html.escape(name,quote=True)+'">'+html.escape(name)+'</a>' for name in artists(track)]
        self.now_artist.setText(' · '.join(links));self.now_artist.setToolTip(track.get('artist',''))
        self.favorite_button.setEnabled(bool(self.current_key));self.favorite_button.setChecked(self.current_key in self.favorite_keys)
        self.now_cover.image=QPixmap();self.now_cover.title=track.get('title','Música');self.now_cover.update();self.apply_cover(self.current_key,self.now_cover)
        from ui_motion import reveal_content
        reveal_content(self.now_cover,metric('motion_fast'))
        self.request_track_cover(self.current_key)
        if self.lyrics_panel.isVisible():self.request_lyrics()

    def play_view(self):
        keys=self.all_keys() if self.view=='home' else self.visible_keys
        if keys:
            self.visible_keys=keys;self.play_key(keys[0])

    def shuffle_view(self):
        self.shuffle.setChecked(True);self.play_view()

    def play_key(self,key,keep_queue=False):
        if not self.available(key):return
        if not keep_queue:
            self.order.start(self.visible_keys or self.all_keys(),key,self.shuffle.isChecked())
            self.order.repeat=self.repeat.isChecked();self.queue=self.order.keys.copy()
        self.current_key=key;track=self.playable(key);self.current_audio=track.copy();self.pending_path=track['path'];self.ended=False;self.current_position=0
        self.duration=track.get('duration',0);self.seek.setRange(0,round(self.duration));self.seek.setValue(0);self.total.setText(stamp(self.duration));self.elapsed.setText('0:00')
        self.show_current();self.status.clear()
        if self.socket is not None:self.load_pending()
        elif self.process.state()==self.process.ProcessState.NotRunning:self.start_player()
        self.render_tracks();self.save_session()

    def advance(self,direction,automatic=False):
        key=self.order.move(direction,self.available)
        if key:self.play_key(key,keep_queue=True)
        elif automatic:
            self.ended=True;self.set_paused(True);self.status.setText('Terminó la lista · pulsa reproducir para escuchar de nuevo')
        self.update_actions()

    def change_shuffle(self):
        if self.current_key:
            # Preserve past navigation; shuffle only the unvisited future.
            cursor=self.order.index
            future=self.order.keys[cursor+1:]
            if self.shuffle.isChecked():__import__('random').shuffle(future)
            else:future=[k for k in self.order.source if k in future]
            self.order.keys=self.order.keys[:cursor+1]+future
            self.order.shuffle=self.shuffle.isChecked();self.queue=self.order.keys.copy()
        self.save_session()

    def change_repeat(self):
        self.order.repeat=self.repeat.isChecked();self.update_actions();self.save_session()

    def update_actions(self):
        if not hasattr(self,'play_button'):return
        self.play_button.setEnabled(bool(self.current_key or self.visible_keys))
        self.favorite_button.setEnabled(bool(self.current_key))
        self.previous_button.setEnabled(bool(self.order.keys) and (self.order.index>0 or self.repeat.isChecked()))
        self.next_button.setEnabled(bool(self.order.keys) and (self.order.index<len(self.order.keys)-1 or self.repeat.isChecked()))
        self.hero_play.setEnabled(bool(self.visible_keys or (self.view=='home' and self.all_keys())))
        self.hero_shuffle.setEnabled(self.hero_play.isEnabled())

    def set_paused(self,value):
        self.paused=bool(value);self.play_button.setText('');self.play_button.setIcon(icon('play' if self.paused else 'pause',17,'on_accent'))
        name='Reproducir' if self.paused else 'Pausar';self.play_button.setToolTip(name+' · Ctrl+Espacio');self.play_button.setAccessibleName(name)

    def toggle_play(self):
        if self.current_key and (self.socket is None or self.ended):
            position=0 if self.ended else self.current_position
            self.resume_position=position;self.resume_paused=False
            self.play_key(self.current_key,keep_queue=bool(self.order.keys))
        elif self.current_key:self.command(['cycle','pause'])
        else:self.play_selection() if self.pages.currentIndex()==0 and self.tree.currentItem() else self.play_view()

    def load_pending(self):
        if self.pending_path:
            position=getattr(self,'resume_position',0);paused=getattr(self,'resume_paused',False)
            legacy=getattr(self,'legacy_endpoint',None)
            if legacy:
                import socket
                try:
                    with socket.socket(socket.AF_UNIX) as previous:
                        previous.settimeout(.3);previous.connect(legacy)
                        previous.sendall((json.dumps({'command':['set_property','pause',True]})+'\n').encode())
                except OSError:pass
                self.legacy_endpoint=None
            self.command(['loadfile',self.pending_path,'replace',-1,{'start':str(position)}])
            self.command(['set_property','pause',paused]);self.pending_path=None
            self.resume_position=0;self.resume_paused=False;self.set_paused(paused)

    def read_player(self):
        super().read_player()
        # time-pos is kept at mpv precision, independent from the integer slider.
        if self.lyric_rows and self.lyrics_panel.isVisible():
            offset=self.store.get('offset:'+str(self.current_key),0)
            index=bisect.bisect_right([row[0] for row in self.lyric_rows],self.current_position+offset)-1
            if index!=self.lyric_index:
                if 0<=self.lyric_index<self.lyric_list.count():
                    old=self.lyric_list.item(self.lyric_index);old.setForeground(color('subtle'));self.lyric_font(old,16)
                self.lyric_index=index
                if 0<=index<self.lyric_list.count():
                    item=self.lyric_list.item(index);item.setForeground(color('text'));self.lyric_font(item,21);self.scroll_lyric(item)

    def lyric_font(self,item,size):
        from PySide6.QtGui import QFont
        font=QFont(self.font());font.setPixelSize(size);font.setWeight(QFont.DemiBold);item.setFont(font)

    def size_lyric(self,item):
        from PySide6.QtGui import QFont,QFontMetrics
        from PySide6.QtCore import QRect
        self.lyric_font(item,metric('font_heading'))
        font=QFont(item.font());font.setPixelSize(metric('font_title'))
        width=max(230,self.lyrics_panel.width()-50)
        bounds=QFontMetrics(font).boundingRect(QRect(0,0,width,1000),Qt.TextWordWrap,item.text())
        item.setSizeHint(QSize(width,max(48,bounds.height()+24)))

    def player_error(self,message):
        super().player_error(message);self.status.show()

    def scroll_lyric(self,item):
        from PySide6.QtCore import QPropertyAnimation,QEasingCurve
        from ui_motion import reduced_motion
        if self.lyric_list.hasFocus():return # Let keyboard readers choose a line without losing their place.
        scrollbar=self.lyric_list.verticalScrollBar();start=scrollbar.value()
        self.lyric_list.setCurrentItem(item);self.lyric_list.scrollToItem(item,QAbstractItemView.PositionAtCenter)
        end=scrollbar.value()
        if reduced_motion(self):return
        scrollbar.setValue(start)
        if self.lyric_scroll_animation is None:self.lyric_scroll_animation=QPropertyAnimation(scrollbar,b'value',self)
        animation=self.lyric_scroll_animation;animation.stop();animation.setDuration(metric('motion_fast'));animation.setStartValue(start);animation.setEndValue(end);animation.setEasingCurve(QEasingCurve.OutCubic);animation.start()

    def seek_to(self,value):
        if not self.current_key:return
        if self.socket is None or self.ended:
            self.resume_position=value;self.resume_paused=self.paused
            self.play_key(self.current_key,keep_queue=bool(self.order.keys))
        else:self.command(['seek',value,'absolute'])

    def position_changed(self,value):
        self.current_position=float(value)

    def toggle_lyrics(self):
        show=not self.lyrics_panel.isVisible()
        if show and self.width()<1280:
            screen=self.screen().availableGeometry();self.resize(min(1360,screen.width()-32),self.height())
        self.lyrics_panel.setVisible(show)
        self.adapt_lyrics()
        if show:self.request_lyrics()

    def request_lyrics(self):
        self.lyric_rows=[];self.lyric_index=-1;self.lyric_list.clear()
        if not self.current_key:self.lyric_status.setText('Reproduce una canción para ver su letra.');return
        track=self.current_audio or self.playable(self.current_key);self.lyric_title.setText(track['title'])
        self.lyric_key=self.current_key+':'+str(round(track.get('duration',0),2))
        preferred=self.playable(self.current_key)
        self.audio_version_button.setVisible(preferred.get('path')!=track.get('path'))
        self.lyric_status.setText('Buscando letra…');self.offset_label.setText(f'{self.store.get("offset:"+self.current_key,0):+.1f} s')
        if not self.test:self.metadata.lyrics(self.lyric_key,dict(track,title=self.state['tracks'][self.current_key]['title'],artist=self.state['tracks'][self.current_key]['artist']),self.store.reference(self.current_key))

    def show_lyrics(self,data):
        self.lyric_rows=parse_lrc(data.get('synced'));self.lyric_index=-1;self.lyric_list.clear()
        if self.lyric_rows:
            self.lyric_status.setText('Sincronizada · LRCLIB')
            for position,text in self.lyric_rows:
                item=QListWidgetItem(text);item.setData(Qt.UserRole,position);item.setForeground(color('subtle'));self.lyric_list.addItem(item);self.size_lyric(item)
        elif data.get('instrumental'):self.lyric_status.setText('Instrumental · no hay letra')
        elif data.get('plain'):
            self.lyric_status.setText('Letra sin sincronizar · LRCLIB')
            for line in data['plain'].splitlines():
                item=QListWidgetItem(line or ' ');self.lyric_list.addItem(item);self.size_lyric(item)
        else:self.lyric_status.setText('La letra no está disponible para esta versión.')

    def seek_lyric(self,item):
        position=item.data(Qt.UserRole)
        if position is not None:self.seek_to(max(0,position-self.store.get('offset:'+str(self.current_key),0)))

    def offset_lyrics(self,amount):
        if not self.current_key or not self.lyric_rows:return
        value=round(self.store.get('offset:'+self.current_key,0)+amount,1)
        self.store.put('offset:'+self.current_key,value);self.offset_label.setText(f'{value:+.1f} s')

    def mute(self):
        if self.volume.value():self.last_volume=self.volume.value();self.volume.setValue(0)
        else:self.volume.setValue(getattr(self,'last_volume',60))

    def toggle_details(self):
        self.download_log.setVisible(not self.download_log.isVisible());self.details.setText('Ocultar detalles' if self.download_log.isVisible() else 'Mostrar detalles')

    def render_downloads(self):
        counts={s:sum(t.get('status')==s for t in self.state['tracks'].values()) for s in STATUS}
        self.download_status.setText(f'{counts["ready"]} guardadas · {counts["pending"]+counts["downloading"]} en cola · {counts["review"]+counts["error"]} requieren atención'+(' · cola pausada' if self.state.get('paused') else ''))
        self.download_list.clear();lines=[]
        for track in self.state['tracks'].values():
            if track.get('status')=='ready':continue
            item=QListWidgetItem(track['title']+'\n'+STATUS.get(track['status'],track['status'])+' · '+track['artist']);self.download_list.addItem(item)
            lines.append(track['title']+'\n'+(track.get('progress') or track.get('error') or 'Esperando turno'))
        if not self.download_list.count():self.download_list.addItem('Tu música está lista para escuchar.')
        self.download_log.setPlainText('\n\n'.join(lines))
        self.resume_button.setEnabled(bool(counts['pending'] or counts['downloading']))
        self.pause_downloads_button.setEnabled(not self.state.get('paused') and bool(counts['pending'] or counts['downloading']))

    def enqueue_results(self):
        super().enqueue_results()
        if not self.test:self.go('downloads')

    def save_session(self):
        if self.test:return
        self.store.put('session',dict(track=self.current_key,position=self.current_position,ended=self.ended,volume=self.volume.value(),shuffle=self.shuffle.isChecked(),repeat=self.repeat.isChecked(),view=self.view,collection=self.collection,artist=self.artist_name,order=self.order.export()))

    def quit_app(self):
        self.shutdown_jobs();QApplication.instance().exit(0)

    def shutdown_jobs(self):
        if self.stopping:return
        self.save_session();self.save_timer.stop();super().shutdown_jobs()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'lyrics_panel'):self.adapt_lyrics()

    def search_online(self):
        query=self.online_query.text().strip()
        if 'open.spotify.com' in query or query.startswith('spotify:'):
            from music_spotify import import_link,spotify_entity
            try:spotify_entity(query)
            except ValueError as error:self.online_status.setText(str(error));return
            self.online_button.setEnabled(False);self.online_status.setText('Leyendo playlist de Spotify…')
            self.metadata.request('spotify-import',query,lambda:import_link(query))
        else:super().search_online()

    def spotify_import_ready(self,data):
        self.online_button.setEnabled(True)
        if data.get('error'):self.online_status.setText(data['error']);return
        from music_data import equivalent_track
        tracks=data['collections'][0]['tracks'];existing=sum(equivalent_track(self.state,t) in self.state['tracks'] for t in tracks)
        self.store.import_references(data);music.enqueue(data);music.start_worker();self.refresh(True)
        self.request_collection_covers()
        self.online_status.setText(f"{len(tracks)} canciones publicadas por Spotify · {existing} reutilizadas · {len(tracks)-existing} añadidas a la cola")
        self.go('tracks',data['collections'][0]['id'])
        self.summary.setText(f"{len(tracks)} publicadas por Spotify · {existing} ya estaban en tu biblioteca")

    def adapt_lyrics(self):
        compact=self.lyrics_panel.isVisible() and self.width()<1100
        self.sidebar.setVisible(not compact);self.center.setVisible(not compact)
        self.lyrics_panel.setFixedWidth(max(260,self.width()-44) if compact else 320)
        for i in range(self.lyric_list.count()):self.size_lyric(self.lyric_list.item(i))
