# Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
# Fuente: 507d66285e9d9fde9330adc64159cfdebb28c19a; véase THIRD_PARTY.md.
# Los QML de origen no incluyen avisos de copyright adicionales por archivo.
"""Color workbench: editable values, screen sampling and reusable palettes."""
from theme_tokens import apply_style

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPixmap, QPainter, QIcon, QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QVBoxLayout, QLineEdit,
    QLabel, QListWidget, QListWidgetItem, QWidget, QComboBox, QSlider, QSplitter)
from utility_material import MaterialSurface as Surface, button, surface, metrics
from desktop_common import  text_label
from utility_data import Colors
from color_data import parse_color


def contrast_text(color):
    def linear(v): return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
    lum = sum(w*linear(v) for w,v in zip((.2126,.7152,.0722),color.getRgbF()[:3]))
    black = (lum+.05)/.05; white = 1.05/(lum+.05)
    return ('#111111', black) if black >= white else ('#FFFFFF', white)  # theme-exception: texto sobre el color del usuario


class ColorWindow(Surface):
    def __init__(self, path=None):
        super().__init__('Wysun Colors', 'WYSUN  /  Del escritorio a tu próximo proyecto', 800, 620)
        self.store = Colors(path); self.picker = None; self.syncing = False
        self.color = QColor('#7AA2F7')  # theme-exception: color inicial de muestra
        workspace = QSplitter(); self.workspace = workspace; workspace.setChildrenCollapsible(False)
        work = surface(QWidget()); work_layout = QVBoxLayout(work)
        palette = surface(QWidget(), 'navigation'); palette_layout = QVBoxLayout(palette)
        gap = metrics()['gap']
        for layout in (work_layout, palette_layout):
            layout.setContentsMargins(gap, gap, gap, gap); layout.setSpacing(metrics()['space_s'])
        work_layout.addWidget(text_label('Color', 'title'))
        palette_layout.addWidget(text_label('Tu paleta', 'title'))
        palette_layout.addWidget(text_label('Recientes y favoritos', 'sectionLabel'))
        top = QHBoxLayout(); self.entry = QLineEdit(self.color.name().upper()); self.entry.setPlaceholderText('HEX, rgb(122, 162, 247), hsl(221, 89%, 72%)…'); top.addWidget(self.entry, 1)  # theme-exception: ejemplo de formatos en el texto de ayuda
        top.addWidget(button('Capturar  Ctrl P', self.capture, 'primary', 'palette')); work_layout.addLayout(top)
        body = QVBoxLayout(); body.setSpacing(gap)
        visual = QVBoxLayout(); self.swatch = QLabel(); self.swatch.setAlignment(Qt.AlignCenter); self.swatch.setMinimumSize(280, 210); visual.addWidget(self.swatch, 1)
        self.contrast = text_label('', 'subtitle'); visual.addWidget(self.contrast); body.addLayout(visual, 1)
        values = QVBoxLayout(); values.setSpacing(10); self.fields = {}; self.formats = QComboBox(); self.formats.hide()
        for name in ('HEX', 'RGB', 'HSL'):
            row = QHBoxLayout(); tag = text_label(name, 'subtitle'); tag.setFixedWidth(32); row.addWidget(tag)
            field = QLineEdit(); field.setReadOnly(True); self.fields[name] = field; row.addWidget(field, 1)
            copy = button('', lambda n=name: self.copy_format(n), symbol='copy'); copy.setToolTip('Copiar '+name); row.addWidget(copy); values.addLayout(row)
        self.sliders = []
        for name, maximum in [('Matiz', 359), ('Saturación', 100), ('Luminosidad', 100)]:
            row = QHBoxLayout(); tag = text_label(name, 'subtitle'); tag.setFixedWidth(84); row.addWidget(tag)
            slider = QSlider(Qt.Horizontal); slider.setRange(0, maximum); slider.valueChanged.connect(self.adjust); row.addWidget(slider); self.sliders.append(slider); values.addLayout(row)
        self.star = button('Guardar favorito', self.favorite, symbol='pin'); self.star.setCheckable(True); values.addWidget(self.star); body.addLayout(values, 1); work_layout.addLayout(body, 1)
        self.filter = QComboBox(); self.filter.addItems(['Recientes y favoritos', 'Solo favoritos']); palette_layout.addWidget(self.filter)
        self.recent = QListWidget(); self.recent.setViewMode(QListWidget.IconMode); self.recent.setResizeMode(QListWidget.Adjust); self.recent.setMovement(QListWidget.Static); self.recent.setIconSize(QSize(66, 36)); self.recent.setGridSize(QSize(104, 84)); self.recent.setMinimumWidth(metrics()['rail_width']); palette_layout.addWidget(self.recent, 1)
        workspace.addWidget(palette); workspace.addWidget(work); workspace.setSizes([metrics()['rail_width'] + metrics()['space_xl'], 520]); self.outer.addWidget(workspace, 1)
        footer = QHBoxLayout(); self.status = text_label('Selecciona un color o captura cualquier píxel', 'subtitle'); footer.addWidget(self.status, 1)
        self.more = button('Acciones  Alt K', self.actions); footer.addWidget(self.more); self.outer.addLayout(footer)
        self.entry.textChanged.connect(self.update_color); self.filter.currentIndexChanged.connect(self.refresh)
        self.recent.itemClicked.connect(self.choose); self.recent.itemActivated.connect(self.choose)
        for key, fn in [('Ctrl+C', self.copy), ('Ctrl+P', self.capture), ('Alt+K', self.actions)]: QShortcut(QKeySequence(key), self).activated.connect(fn)
        self.update_color(); self.refresh()

    def update_color(self, *_):
        c = parse_color(self.entry.text()); self.formats.clear(); valid = c.isValid(); self.star.setEnabled(valid)
        apply_style(self.entry,'' if valid else 'border-color:@danger;')
        if not valid:
            for field in self.fields.values(): field.clear()
            self.status.setText('Introduce HEX, RGB o HSL válido (sin transparencia)'); return
        self.color = c; value = c.name().upper(); h, s, l, _ = c.getHslF()
        formats = [value, f'rgb({c.red()}, {c.green()}, {c.blue()})', f'hsl({max(0,h)*360:.0f}, {s*100:.0f}%, {l*100:.0f}%)']  # theme-exception: formatos de color para copiar
        self.formats.addItems(formats)
        for field, text in zip(self.fields.values(), formats): field.setText(text)
        ink, ratio = contrast_text(c)
        apply_style(self.swatch,f'background:{value};border:@border solid @line;border-radius:@radius_l;color:{ink};font-size:@font_title;font-weight:600;'); self.swatch.setText(value)
        self.contrast.setText(f'Texto recomendado: {"oscuro" if ink == "#111111" else "blanco"}  ·  Color opaco')  # theme-exception: tinta de texto sobre el color elegido por el usuario
        self.syncing = True
        for slider, v in zip(self.sliders, (max(0,h)*360, s*100, l*100)): slider.setValue(min(slider.maximum(),round(v)))
        self.syncing = False; self.update_star(); self.status.setText('Copia un formato · Los colores copiados se guardan en recientes')

    def adjust(self, *_):
        if self.syncing: return
        h,s,l = [x.value() for x in self.sliders]; self.entry.setText(QColor.fromHslF(h/360, s/100, l/100).name().upper())

    def update_star(self):
        favorite = self.color.name().upper() in self.store.read().get('favorites', [])
        self.star.setChecked(favorite); self.star.setText('En favoritos' if favorite else 'Guardar favorito')

    def refresh(self, *_):
        self.recent.clear(); data = self.store.read()
        rows = data.get('favorites', []) + ([] if self.filter.currentIndex() else data.get('recent', []))
        for value in dict.fromkeys(rows):
            color = parse_color(value)
            if not color.isValid(): continue
            pix = QPixmap(132,72); pix.fill(Qt.transparent); p = QPainter(pix); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen); p.setBrush(color); p.drawRoundedRect(1,1,130,70,10,10); p.end(); pix.setDevicePixelRatio(2)
            item = QListWidgetItem(QIcon(pix), ('★ ' if value in data.get('favorites',[]) else '')+value); item.setData(Qt.UserRole,value); self.recent.addItem(item)
        self.update_star()

    def choose(self, item): self.entry.setText(item.data(Qt.UserRole))

    def copy_format(self, name):
        if not self.formats.count(): return
        QApplication.clipboard().setText(self.fields[name].text()); self.store.save(self.color.name().upper()); self.refresh(); self.status.setText(name+' copiado al portapapeles')

    def copy(self):
        self.copy_format(('HEX','RGB','HSL')[max(0,self.formats.currentIndex())])

    def favorite(self):
        if self.formats.count(): self.store.save(self.color.name().upper(), True); self.refresh()

    def paste(self): self.entry.setText(QApplication.clipboard().text().strip())

    def actions(self):
        from enhanced import SearchMenu
        entries = [('Pegar color del portapapeles', '', self.paste)]
        if self.formats.count():
            entries += [('Copiar variable CSS', '', lambda: QApplication.clipboard().setText('--color: '+self.color.name().upper()+';'))]
        if self.store.read().get('favorites'):
            entries += [('Copiar paleta CSS', '', self.copy_palette)]
        self.popup = SearchMenu(self, entries); self.popup.present(self.more)

    def copy_palette(self):
        values = self.store.read().get('favorites',[])
        QApplication.clipboard().setText(':root {\n'+'\n'.join(f'  --color-{i}: {c};' for i,c in enumerate(values,1))+'\n}'); self.status.setText('Paleta CSS copiada')

    def capture(self):
        from PySide6.QtCore import QTimer
        self.hide(); QTimer.singleShot(180, self.start_picker)

    def start_picker(self):
        from PySide6.QtCore import QProcess
        import json,shutil
        executable=shutil.which('wysun')
        if not executable:
            self.present();self.status.setText('Falta el lanzador Wysun Recorder para acceder al selector de color del portal.');return
        self.portal_picker=QProcess(self)
        def finished(code,*_):
            try:
                if code:raise ValueError('Selección cancelada o portal de color no disponible')
                values=json.loads(bytes(self.portal_picker.readAllStandardOutput()))
                if len(values)!=3 or not all(0<=v<=1 for v in values):raise ValueError('Color inválido')
                self.picked(QColor.fromRgbF(*values))
            except (ValueError,TypeError):self.present();self.status.setText('Selección cancelada o portal de color no disponible')
            self.portal_picker.deleteLater()
        self.portal_picker.finished.connect(finished)
        self.portal_picker.errorOccurred.connect(lambda *_:(self.present(),self.status.setText('No se pudo abrir el selector de color del portal.')))
        self.portal_picker.start(executable,['recorder','--pick-color'])

    def picked(self, color):
        self.entry.setText(color.name().upper()); self.store.save(color.name().upper()); self.refresh(); self.present()
