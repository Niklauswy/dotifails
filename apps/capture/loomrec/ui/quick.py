"""Compact capture surface using the full application's source-of-truth controls."""
from ..portal import is_wayland
from PySide6.QtCore import Qt,QTimer,QPoint,QSize
from PySide6.QtGui import QCursor,QShortcut,QKeySequence
from PySide6.QtWidgets import QApplication,QWidget,QHBoxLayout,QVBoxLayout,QFormLayout,QLabel,QDialog,QListWidget,QListWidgetItem,QScrollArea,QFrame,QSizePolicy
from .materials import apply_material
from .components import DeviceChoices,SoftButton,ComboBox,SpinBox,DoubleSpinBox,CheckBox,surface,label


class WindowChooser(QDialog):
    def __init__(self,owner):
        super().__init__(owner.quick if owner.quick_mode else owner)
        self.owner=owner;self.selecting=False;self.closed=False;self.refresh_id=0;self.refresh_busy=False
        self.setWindowTitle(self.tr('Elegir ventana · Wysun Recorder'));self.resize(580,460);self.setMinimumSize(380,340)
        layout=QVBoxLayout(self);layout.setContentsMargins(22,22,22,20);layout.setSpacing(14)
        layout.addWidget(label(self.tr('Elige una ventana'),'title'))
        hint=label(self.tr('La llevaremos a la vista. Mantén su contenido visible mientras grabas.'),'subtitle');hint.setWordWrap(True);layout.addWidget(hint)
        from .components import WindowDelegate
        self.items=QListWidget();self.items.setItemDelegate(WindowDelegate(self.items));self.items.setSpacing(4);self.items.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.items.setVerticalScrollMode(QListWidget.ScrollPerPixel);self.items.setAccessibleName(self.tr('Ventanas disponibles'));layout.addWidget(self.items,1)
        self.empty=label(self.tr('Buscando ventanas…'),'section');self.empty.setAlignment(Qt.AlignCenter);self.empty.setWordWrap(True);layout.addWidget(self.empty,1)
        self.status=label(self.tr('Buscando ventanas…'),'subtitle');self.status.setWordWrap(True);layout.addWidget(self.status)
        footer=QHBoxLayout();layout.addLayout(footer);footer.addStretch()
        cancel=SoftButton(self.tr('Cancelar'),quiet=True);cancel.clicked.connect(self.reject);footer.addWidget(cancel)
        self.choose=SoftButton(self.tr('Usar ventana'),'check',primary=True);self.choose.setEnabled(False);self.choose.setDefault(True);self.choose.clicked.connect(self.select);footer.addWidget(self.choose)
        self.items.currentRowChanged.connect(lambda _:self.choose.setEnabled(not self.selecting and self.items.currentItem() is not None));self.items.itemActivated.connect(self.select)
        self.refresh_timer=QTimer(self);self.refresh_timer.setInterval(5000);self.refresh_timer.timeout.connect(self.refresh)
        self.items.hide();apply_material(self,kind='dialog',radius=20)
    def showEvent(self,event):
        super().showEvent(event)
        if not self.closed:self.refresh_timer.start();self.refresh()
    def hideEvent(self,event):
        self.refresh_timer.stop();super().hideEvent(event)
    def refresh(self):
        if self.selecting or self.closed or self.refresh_busy or not self.isVisible():return
        from ..devices import list_windows
        self.refresh_busy=True;self.refresh_id+=1;request=self.refresh_id
        if not self.items.count():self.status.setText(self.tr('Buscando ventanas…'))
        def work():
            try:return list_windows(),None
            except Exception as exc:return [],str(exc)
        def ready(result):
            self.refresh_busy=False
            if request!=self.refresh_id or self.closed or self.selecting or not self.isVisible():return
            windows,error=result if isinstance(result,tuple) else (result,None)
            if error:
                self.status.setText(self.tr('No se pudo actualizar la lista. Se reintentará automáticamente.'));self.status.setToolTip(error)
                if not self.items.count():self.empty.setText(self.tr('No pudimos leer las ventanas'))
                return
            self.ready(windows)
        self.owner.task(work,ready)
    def ready(self,windows):
        current=self.items.currentItem();selected=current.data(Qt.UserRole)['id'] if current else None
        scroll=self.items.verticalScrollBar().value();focus=self.focusWidget()
        owned={int(w.winId()) for w in QApplication.topLevelWidgets()}
        entries=[entry for entry in windows if int(entry['id'],16) not in owned]
        self.items.blockSignals(True);self.items.clear();found=False
        for entry in entries:
            desktop=entry.get('desktop')
            location=self.tr('Todos los escritorios') if desktop==0xffffffff else self.tr('Escritorio ')+str(desktop+1) if desktop is not None else ''
            secondary=' · '.join(value for value in [entry.get('app',''),location,self.tr('Minimizada · se restaurará') if entry.get('hidden') else ''] if value)
            item=QListWidgetItem(entry['title']+'\n'+secondary);item.setData(Qt.UserRole,entry);item.setToolTip(entry['title']+'\n'+secondary);self.items.addItem(item)
            if entry['id']==selected:self.items.setCurrentItem(item);found=True
        self.items.blockSignals(False);self.items.doItemsLayout();self.items.verticalScrollBar().setValue(scroll)
        self.choose.setEnabled(found);self.items.setVisible(bool(entries));self.empty.setVisible(not entries);self.empty.setText(self.tr('No hay ventanas disponibles'))
        self.status.setText(self.tr('La ventana seleccionada ya no está disponible.') if selected and not found else self.tr('Actualización automática · elige con las flechas y confirma con Enter.'))
        if focus and focus.isVisible():focus.setFocus(Qt.OtherFocusReason)
    def select(self,*_):
        if self.selecting or self.closed:return
        item=self.items.currentItem()
        if not item:return
        entry=item.data(Qt.UserRole)
        self.selecting=True;self.choose.setEnabled(False);self.hide();self.owner.hide();self.owner.quick.hide_all()
        def activate():
            from ..devices import activate_window
            try:return activate_window(entry['id']),None
            except Exception as exc:return None,str(exc)
        def applied(result):
            if self.closed:return
            self.selecting=False;rect,error=result
            if error:
                self.show();self.status.setText(error);self.choose.setEnabled(self.items.currentItem() is not None);return
            self.owner.window_target=entry['id']
            for widget,value in zip(self.owner.rect,rect):widget.setValue(value)
            self.owner.quick_mode=True;self.accept()
        self.owner.task(activate,applied)
    def done(self,result):
        if self.selecting:return
        self.closed=True;self.refresh_id+=1;self.refresh_timer.stop();super().done(result)


class QuickBar(QWidget):
    def __init__(self,owner):
        super().__init__(None,Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.owner=owner;self.popup=None;self.setWindowTitle('Wysun Recorder · Captura rápida');self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName('quickBar')
        self.setStyleSheet('#quickBar {color:#445E7A;} #quickBar > QPushButton {font-size:14px;color:#445E7A;border-radius:20px;padding:10px 14px;} #quickBar > QPushButton[primary="true"] {color:white;font-size:16px;font-weight:600;border-radius:26px;} #quickBar > QPushButton[quiet="true"] {background:transparent;border-color:transparent;} #quickBar > QPushButton[quiet="true"]:hover {background:rgba(255,255,255,90);} #quickBar > QPushButton:focus {border:2px solid #4179C2;} #quickBar > QPushButton[sourceActive="true"] {background:#D9E9FC;border:1px solid #A9C7EB;} #quickBar > QPushButton[sourceUnavailable="true"] {background:#F7EDD9;border:1px solid #D6B879;}')
        self.row=QHBoxLayout(self);self.row.setContentsMargins(20,16,20,16);self.row.setSpacing(8)
        self.source_buttons=[]
        self.mode=SoftButton(self.tr('Pantalla ⌄'),'screen',quiet=True);self.mode.setMinimumWidth(148);self.mode.clicked.connect(lambda:self.sources(self.mode));self.row.addWidget(self.mode,2)
        for name,symbol,source in [(self.tr('Cámara'),'camera',owner.camera),(self.tr('Micrófono'),'mic',owner.mic),(self.tr('Audio del equipo'),'sound',owner.system)]:
            b=SoftButton('⌄',symbol,quiet=True);b.setAccessibleName(name);b.setToolTip(name);b.setMinimumWidth(58);b.clicked.connect(lambda _,b=b,c=source,n=name:self.device(b,c,n));self.row.addWidget(b,1);self.source_buttons.append(b)
        self.options=SoftButton('','settings',quiet=True);self.options.setAccessibleName(self.tr('Opciones y atajos'));self.options.setToolTip(self.tr('Opciones y atajos'));self.options.setFixedWidth(48);self.options.clicked.connect(self.settings);self.row.addWidget(self.options)
        self.start=SoftButton(self.tr('Grabar'),'record',primary=True);self.start.setMinimumWidth(142);self.start.clicked.connect(self.begin);self.row.addWidget(self.start,2)
        self.dismiss=SoftButton('×',quiet=True);self.dismiss.setFixedWidth(44);self.dismiss.setAccessibleName(self.tr('Cerrar barra'));self.dismiss.setToolTip(self.tr('Cerrar barra · Esc'));self.dismiss.clicked.connect(self.escape);self.row.addWidget(self.dismiss)
        for b in [self.mode,*self.source_buttons,self.options,self.start,self.dismiss]:b.setProperty('hoverRadius',26 if b is self.start else 20);b.setFixedHeight(52);b.setIconSize(QSize(24,24));b.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed)
        self.status=label('', 'subtitle');self.status.setParent(self);self.status.hide()
        apply_material(self,kind='quick',radius=44)
        QShortcut(QKeySequence('Escape'),self,activated=self.escape)
        self.timer=QTimer(self);self.timer.timeout.connect(self.sync);self.timer.start(150)
    def escape(self):
        if self.owner.capture_pending:self.owner.cancel_countdown()
        self.hide_all()
    def hide_all(self):
        if hasattr(self.owner,'recording_indicator') and not self.owner.session and not self.owner.capture_pending:self.owner.recording_indicator.hide()
        if self.popup:self.popup.close();self.popup=None
        self.hide()
        if hasattr(self.owner,'camera_preview'):self.owner.camera_preview.stop()
    def present(self):
        self.hide_all();self.owner.hide();self.owner.quick_mode=True;self.sync()
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();geo=screen.availableGeometry()
        width=min(720,max(320,geo.width()-32))
        compact=width<660
        self.row.setContentsMargins(12 if compact else 20,16,12 if compact else 20,16);self.row.setSpacing(4 if compact else 8)
        self.mode.setMinimumWidth(54 if compact else 148);self.mode.setText('⌄' if compact else self.mode.text()+' ⌄')
        self.start.setMinimumWidth(88 if width<580 else 110 if compact else 142)
        for b in self.source_buttons:b.setMinimumWidth(44 if compact else 58);b.setVisible(width>=580)
        self.setFixedSize(width,88)
        self.move(max(geo.left(),geo.center().x()-self.width()//2),max(geo.top(),geo.bottom()-self.height()-28))
        # Capture the destination before mapping. Never focus the old desktop.
        import os,subprocess
        desktop=None
        if not is_wayland() and os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            try:desktop=subprocess.check_output(['bspc','query','-D','-d','focused'],text=True,timeout=.5).strip()
            except (OSError,subprocess.SubprocessError):pass
        self.show();self.raise_()
        def focus_here():
            if not self.isVisible():return
            if desktop:
                try:
                    current=subprocess.check_output(['bspc','query','-D','-d','focused'],text=True,timeout=.5).strip()
                    if current!=desktop:return
                    node=hex(int(self.winId()))
                    subprocess.run(['bspc','node',node,'-d',desktop],capture_output=True,timeout=.5,check=True)
                    subprocess.run(['bspc','node',node,'-f'],capture_output=True,timeout=.5,check=True)
                except (OSError,subprocess.SubprocessError):return
            self.activateWindow()
        focus_here();QTimer.singleShot(100,self,focus_here)
        self.owner.selection_feedback()
    def pop(self,anchor,title):
        if self.popup:self.popup.close()
        popup=QWidget(self,Qt.Popup);popup.setWindowTitle(title);popup.setMinimumWidth(364);popup.setMaximumWidth(440)
        layout=QVBoxLayout(popup);layout.setContentsMargins(18,18,18,18);layout.setSpacing(14);layout.addWidget(label(title,'section'))
        apply_material(popup,kind='popup',radius=20)
        self.popup=popup;return popup,layout
    def show_pop(self,popup,anchor):
        popup.adjustSize();point=anchor.mapToGlobal(QPoint(0,0));screen=QApplication.screenAt(point) or QApplication.primaryScreen();geo=screen.availableGeometry()
        popup.move(max(geo.left(),min(point.x(),geo.right()-popup.width())),max(geo.top(),self.y()-popup.height()-8));popup.show()
    def combo(self,source):
        combo=ComboBox();combo.setModel(source.model());combo.setCurrentIndex(source.currentIndex());combo.currentIndexChanged.connect(source.setCurrentIndex)
        source.currentIndexChanged.connect(combo.setCurrentIndex);return combo
    def device(self,anchor,source,title):
        popup,layout=self.pop(anchor,title);symbol='camera' if source is self.owner.camera else 'mic' if source is self.owner.mic else 'sound';layout.addWidget(DeviceChoices(source,symbol))
        if source is self.owner.camera:
            layout.addWidget(self.owner.camera_preview);self.owner.camera_selected()
        self.show_pop(popup,anchor)
    def sources(self,anchor):
        popup,layout=self.pop(anchor,self.tr('Área de captura'));layout.addWidget(label(self.tr('Pantalla'),'subtitle'));layout.addWidget(DeviceChoices(self.owner.monitor,'screen'))
        for title,symbol,fn in [(self.tr('Pantalla completa'),'screen',self.owner.monitor_changed),(self.tr('Seleccionar región…'),'region',self.owner.pick_region),(self.tr('Elegir ventana…'),'window',self.owner.pick_window)]:
            b=SoftButton(title,symbol,quiet=True);b.setMinimumHeight(46);b.setIconSize(QSize(22,22));b.clicked.connect(lambda _,fn=fn:(popup.close(),fn()));layout.addWidget(b)
        hint=label(self.tr('Ventana = recorte visible; no captura oculta.'),'subtitle');layout.addWidget(hint);self.show_pop(popup,anchor)
    def settings(self):
        popup,layout=self.pop(self.options,self.tr('Opciones rápidas'))
        from .cursor_settings import CursorPanel
        layout.addWidget(CursorPanel(self.owner.cursor_options,compact=True))
        form=QFormLayout();layout.addLayout(form)
        if self.width()<580:
            for title,source in [(self.tr('Cámara'),self.owner.camera),(self.tr('Micrófono'),self.owner.mic),(self.tr('Audio del equipo'),self.owner.system)]:
                b=SoftButton(title,quiet=True);b.clicked.connect(lambda _,c=source,t=title:self.device(self.options,c,t));layout.addWidget(b)
        for title,source in [(self.tr('Calidad'),self.owner.quality),(self.tr('FPS'),self.owner.fps)]:form.addRow(title,self.combo(source))
        for title,source in [(self.tr('Cuenta atrás'),self.owner.countdown),(self.tr('Ganancia micrófono'),self.owner.mic_gain),(self.tr('Ganancia equipo'),self.owner.system_gain)]:
            spin=DoubleSpinBox() if isinstance(source,DoubleSpinBox) else SpinBox();spin.setRange(source.minimum(),source.maximum());spin.setValue(source.value());spin.valueChanged.connect(source.setValue);form.addRow(title,spin)
        quiet=CheckBox(self.tr('Pausar notificaciones'));quiet.setChecked(self.owner.quiet.isChecked());quiet.toggled.connect(self.owner.quiet.setChecked);layout.addWidget(quiet)
        refresh=SoftButton(self.tr('Actualizar dispositivos'),'settings');refresh.clicked.connect(self.owner.refresh_devices);layout.addWidget(refresh)
        full=SoftButton(self.tr('Todos los ajustes'),'settings');full.clicked.connect(lambda:(self.escape(),self.owner.show_settings()));layout.addWidget(full)
        full=SoftButton(self.tr('Abrir biblioteca'),'library');full.clicked.connect(lambda:(self.escape(),self.owner.activate_instance('focus')));layout.addWidget(full)
        self.show_pop(popup,self.options)
    def begin(self):
        if self.owner.capture_pending:self.owner.cancel_countdown();return
        if self.popup:self.popup.close()
        self.owner.guard(self.owner.begin_countdown)
    def sync(self):
        w=self.owner
        for button,source,name,symbol in zip(self.source_buttons,[w.camera,w.mic,w.system],[self.tr('Cámara'),self.tr('Micrófono'),self.tr('Audio del equipo')],['camera','mic','sound']):
            unavailable=bool(source.currentData(Qt.UserRole+1));active=source.currentData() is not None and not unavailable
            changed=button.property('sourceActive')!=active or button.property('sourceUnavailable')!=unavailable
            button.setProperty('sourceActive',active);button.setProperty('sourceUnavailable',unavailable)
            description=name+' · '+(self.tr('No disponible') if unavailable else self.tr('Seleccionado') if active else self.tr('Desactivado'))
            if source.currentData() is not None:description+='\n'+source.currentText()
            button.setToolTip(description);button.setAccessibleName(description.replace('\n',': '))
            if changed:
                from .icons import icon
                button.setIcon(icon(symbol,'#87682F' if unavailable else '#2165D5' if active else '#596A80'));button.style().unpolish(button);button.style().polish(button);button.update()
        mode=self.tr('Ventana') if w.window_target or w.capture_modes.buttons()[2].isChecked() else self.tr('Región') if w.capture_modes.buttons()[1].isChecked() else self.tr('Pantalla')
        self.mode.setText((mode if self.width()>=660 else '')+' ⌄');self.mode.setAccessibleName(mode+' · '+self.tr('Elegir área'));self.mode.setToolTip(mode+' · '+self.tr('Elegir área'))
        self.start.setText(self.tr('Cancelar')+' · '+str(w.remaining+1) if w.capture_pending else self.tr('Grabar'))
        self.start.setEnabled(not (w.session or w.job or w.analysis))
        for b in [self.mode,self.options,*self.source_buttons]:b.setEnabled(not w.capture_pending)
        if hasattr(w,'cursor_options'):self.options.setToolTip(self.tr('Opciones y atajos')+' · '+w.cursor_options.summary());self.options.setAccessibleDescription(w.cursor_options.summary())
        self.status.hide();self.status.setText(self.tr('Preparando captura… Esc para cancelar') if w.capture_pending else w.control_hint.text());self.start.setAccessibleDescription(self.status.text());self.start.setToolTip(self.status.text() if w.capture_pending else self.tr('Iniciar grabación'))
