"""Keyboard-first navigation shared by both native music windows."""
from PySide6.QtCore import QObject, QEvent, Qt, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QAbstractItemView, QPushButton, QMessageBox
from theme_tokens import color, extend_style


def shortcut(parent, keys, action, context=Qt.WindowShortcut):
    binding=QShortcut(QKeySequence(keys),parent)
    binding.setContext(context);binding.activated.connect(action)
    return binding


class SongDelegate(QStyledItemDelegate):
    """Two readable, elided lines with stable height and a generous hit area."""
    def sizeHint(self, option, index):return QSize(180,58)

    def paint(self,painter,option,index):
        painter.save()
        rect=option.rect.adjusted(2,2,-2,-2)
        selected=bool(option.state & QStyle.State_Selected)
        hovered=bool(option.state & QStyle.State_MouseOver)
        if selected or hovered:
            painter.setPen(QPen(color('selection_line'),1) if selected else Qt.NoPen)
            painter.setBrush(color('selection' if selected else 'hover'))
            painter.drawRoundedRect(rect,8,8)
        lines=index.data(Qt.DisplayRole).split('\n',1)
        font=option.font;font.setBold(True);painter.setFont(font)
        painter.setPen(color('selection_text' if selected else 'text'))
        bounds=rect.adjusted(12,7,-12,-27)
        painter.drawText(bounds,Qt.AlignVCenter,painter.fontMetrics().elidedText(lines[0],Qt.ElideRight,bounds.width()))
        font.setBold(False);font.setPointSizeF(max(9,font.pointSizeF()-1));painter.setFont(font)
        painter.setPen(color('muted'))
        bounds=rect.adjusted(12,29,-12,-6)
        painter.drawText(bounds,Qt.AlignVCenter,painter.fontMetrics().elidedText(lines[1] if len(lines)>1 else '',Qt.ElideRight,bounds.width()))
        painter.restore()


class KeyboardNavigation(QObject):
    def __init__(self,window,search,results,activate,mini=False):
        super().__init__(window)
        self.window=window;self.search=search;self.results=results;self.activate=activate;self.mini=mini
        # Watch buttons too: Return should activate the focused control, just like Space.
        for widget in [window,*window.findChildren(__import__('PySide6.QtWidgets',fromlist=['QWidget']).QWidget)]:
            widget.installEventFilter(self)
        search.returnPressed.connect(self.open_selection)
        for widget in window.findChildren(QAbstractItemView):
            widget.setToolTip((widget.toolTip()+'\n' if widget.toolTip() else '')+'↑ / ↓ navegar · Enter abrir · Tab cambiar de zona')
            extend_style(widget,'\nQAbstractItemView:focus{border:@border solid @focus;border-radius:8px;}')

    def current(self):
        return self.results.currentItem() or (self.results.item(0) if self.mini else self.results.topLevelItem(0))

    def open_selection(self):
        item=self.current()
        if item:
            self.results.setCurrentItem(item)
            self.activate(item) if self.mini else self.activate()

    def eventFilter(self,obj,event):
        if event.type() not in (QEvent.ShortcutOverride,QEvent.KeyPress):return False
        key=event.key();mods=event.modifiers()
        escape=key==Qt.Key_Escape and (bool(self.search.text()) or (not self.mini and self.window.lyrics_panel.isVisible()))
        navigate=obj is self.search and key in (Qt.Key_Down,Qt.Key_Up) and mods==Qt.NoModifier
        enter=isinstance(obj,QPushButton) and key in (Qt.Key_Return,Qt.Key_Enter) and mods==Qt.NoModifier
        if not (escape or navigate or enter):return False
        if event.type()==QEvent.ShortcutOverride:event.accept();return True
        if escape:
            if self.search.text():self.search.clear();self.search.setFocus()
            else:self.window.toggle_lyrics();self.search.setFocus()
        elif enter:obj.click()
        elif self.mini:
            count=self.results.count()
            if count:self.results.setCurrentRow(max(0,min(count-1,self.results.currentRow()+(1 if key==Qt.Key_Down else -1))))
        else:
            count=self.results.topLevelItemCount()
            if count:
                item=self.results.currentItem();row=self.results.indexOfTopLevelItem(item) if item else -1
                self.results.setCurrentItem(self.results.topLevelItem(max(0,min(count-1,row+(1 if key==Qt.Key_Down else -1)))))
        if navigate and self.current():self.results.scrollToItem(self.current())
        return True


def keyboard_help(window,mini=False):
    text='Ctrl+F: buscar en toda la biblioteca\n↑ / ↓ y Enter: elegir y reproducir\nTab / Shift+Tab: recorrer controles\nEnter / Espacio: activar el control enfocado\nEsc: limpiar búsqueda, cerrar letra o esconder ventana\n\nCtrl+Espacio: pausar / reproducir\nCtrl+← / →: canción anterior / siguiente\nCtrl+↑ / ↓: volumen ±5\nCtrl+Shift+F: favorito de la canción actual\nCtrl+L: abrir y enfocar letra\nFlechas en la barra de tiempo: adelantar / retroceder 5 s'
    text+=('\nCtrl+Enter: abrir la app completa' if mini else '\n\nAlt+1…5: biblioteca, favoritos, artistas, descargas, añadir música\nCtrl+J: enfocar el contenido\nCtrl+O: importar archivos\nF en la tabla: favorito de la canción seleccionada\nCtrl+Enter en la tabla: abrir artista\nCtrl+Enter en resultados de descarga: guardar selección')
    QMessageBox.information(window,'Wysun Music · Teclado',text)


def playback_shortcuts(window,player):
    shortcut(window,'Ctrl+Shift+F',player.favorite_current)
    shortcut(window,'Ctrl+Up',lambda:player.volume.setValue(min(100,player.volume.value()+5)))
    shortcut(window,'Ctrl+Down',lambda:player.volume.setValue(max(0,player.volume.value()-5)))
