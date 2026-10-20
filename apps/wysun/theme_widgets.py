"""Native theme previews; the entire tile is keyboard/click selectable."""
from pathlib import Path
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QPainterPath,QColor,QPen,QFont,QPixmap
from ui_motion import MotionButton
from theme_tokens import THEMES

class ThemeChoice(MotionButton):
    def __init__(self,key,home,parent=None):
        theme=THEMES[key];super().__init__(theme['name'],parent);self.key=key;self.theme=theme
        self.setCheckable(True);self.setMinimumSize(190,320);self.setAccessibleName(theme['name']);self.setAccessibleDescription(theme['description'])
        self.image=QPixmap(str(Path(home)/'.local/share/backgrounds'/theme['wallpaper']))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);theme=self.theme;rect=QRectF(1,1,self.width()-2,self.height()-2)
        p.setBrush(QColor(theme['surface']));p.setPen(QPen(QColor(theme['accent'] if self.isChecked() or self.hasFocus() else theme['muted']),2 if self.isChecked() or self.hasFocus() else 1));p.drawRoundedRect(rect,16,16)
        image_rect=QRectF(12,12,self.width()-24,178);clip=QPainterPath();clip.addRoundedRect(image_rect,9,9);p.save();p.setClipPath(clip)
        if not self.image.isNull():
            scaled=self.image.scaled(int(image_rect.width()),int(image_rect.height()),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap(int(image_rect.center().x()-scaled.width()/2),int(image_rect.center().y()-scaled.height()/2),scaled)
        p.restore();p.setPen(QColor(theme['foreground']));p.setFont(QFont('Inter',16,QFont.DemiBold));p.drawText(18,224,theme['name'])
        p.setPen(QColor(theme['muted']));p.setFont(QFont('Inter',10));p.drawText(QRectF(18,235,self.width()-36,45),Qt.TextWordWrap,theme['description'])
        for i,colour in enumerate((theme['background'],theme['surface'],theme['accent'],theme['palette'][4],theme['palette'][5])):
            p.setPen(QPen(QColor(theme['muted']),.5));p.setBrush(QColor(colour));p.drawEllipse(QRectF(18+i*25,286,16,16))
        if self.isChecked():
            p.setPen(QPen(QColor(theme['accent']),2,Qt.SolidLine,Qt.RoundCap));x=self.width()-31;p.drawLine(x-7,294,x-2,299);p.drawLine(x-2,299,x+8,288)
