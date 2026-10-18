"""Compact resource meters. Text remains the primary, accessible measurement."""
from theme_tokens import ThemeColor, apply_style

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyledItemDelegate

class ResourceDelegate(QStyledItemDelegate):
    def __init__(self,parent=None):super().__init__(parent);self.total_memory=1
    def paint(self,painter,option,index):
        super().paint(painter,option,index)
        if index.column() not in (2,3):return
        row=index.siblingAtColumn(0).data(Qt.UserRole)
        if not row:return
        value=row.get('cpu',0)/100 if index.column()==2 else row.get('memory',0)/max(1,self.total_memory)
        color=ThemeColor('#9DC2FF' if index.column()==2 else '#C4AEF0')
        painter.save();painter.setPen(Qt.NoPen);painter.setBrush(color)
        painter.drawRoundedRect(QRectF(option.rect.x()+8,option.rect.bottom()-4,max(0,option.rect.width()-16)*min(1,value),2),1,1)
        painter.restore()
