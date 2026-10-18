"""Shared, interruptible Qt motion. Actions that transfer focus still hide immediately."""
from theme_tokens import ThemeColor, apply_style

import os
from PySide6.QtCore import (Qt, QSize, QObject, Property, QPropertyAnimation, QParallelAnimationGroup,
                            QEasingCurve, QPoint, QEvent, QAbstractAnimation, QTimer)
from PySide6.QtGui import QColor, QPainter, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionButton


def reduced_motion(widget=None):
    from ui_appearance import read_appearance
    app = QApplication.instance()
    return (os.environ.get('ORBIT_REDUCED_MOTION', '').lower() in ('1', 'true', 'yes')
            or read_appearance()['reduced_motion'] or bool(app and app.property('orbitReducedMotion')) or bool(getattr(widget, 'test', False)))


class WindowMotion:
    """Mixin: entering windows lift 12px; explicit dismissals settle 6px in 140ms."""
    def _motion_init(self):
        if hasattr(self, '_window_motion'):return
        self._window_motion = QParallelAnimationGroup(self)
        self._motion_target = self.pos()
        self._motion_exiting = False
        self._window_motion.finished.connect(self._motion_finished)
        self._motion_enter_timer=QTimer(self);self._motion_enter_timer.setSingleShot(True);self._motion_enter_timer.timeout.connect(self._deferred_top_entry)
        self._motion_move=QPropertyAnimation(self,b'pos');self._window_motion.addAnimation(self._motion_move)
        self._motion_opacity=None
        if QApplication.platformName() not in ('offscreen','minimal'):
            self._motion_opacity=QPropertyAnimation(self,b'windowOpacity');self._window_motion.addAnimation(self._motion_opacity)

    def _animate_window(self, entering):
        from theme_tokens import tokens
        theme=tokens()
        self._motion_init()
        was_running = self._window_motion.state() == QAbstractAnimation.Running
        self._window_motion.stop()
        if not was_running:self._motion_target = self.pos()
        self._motion_exiting = not entering
        if reduced_motion(self):
            self.move(self._motion_target)
            if not entering:self.hide()
            return
        from_top=bool(getattr(self,'motion_from_top',False))
        distance=theme['lift']
        if from_top:
            screen=self.screen();edge=screen.geometry().top() if screen else 0
            distance=-(self.height()+self._motion_target.y()-edge+10)
        start=self.pos() if was_running else self._motion_target+QPoint(0,distance if entering else 0)
        end=self._motion_target+QPoint(0,0 if entering else distance if from_top else distance//2)
        duration=getattr(self,'motion_enter_ms',theme['enter']) if entering else getattr(self,'motion_exit_ms',theme['exit'])
        if self._motion_opacity is not None:
            opacity=self._motion_opacity;opacity.setDuration(duration)
            opacity.setStartValue(self.windowOpacity() if was_running else (0.0 if entering else 1.0));opacity.setEndValue(1.0 if entering else 0.0);opacity.setEasingCurve(QEasingCurve.OutCubic)
        self.move(start)
        move=self._motion_move;move.setDuration(duration);move.setStartValue(start);move.setEndValue(end);move.setEasingCurve(QEasingCurve.OutCubic)
        self._window_motion.start()

    def _motion_finished(self):
        if self._motion_exiting:self.hide()

    def show(self):
        self._motion_init()
        if not self.isVisible():self._motion_target=self.pos()
        if self.isVisible() and self._motion_exiting:self._animate_window(True)
        super().show()

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self,'motion_from_top',False) and not reduced_motion(self):
            # Let X11 map/position the transparent window before starting its descent.
            # Otherwise a window manager's initial centering can overwrite frame one.
            edge=self.screen().geometry().top() if self.screen() else 0
            self.move(self._motion_target.x(),edge-self.height()-10)
            if self._motion_opacity is not None:self.setWindowOpacity(0.)
            self._motion_enter_timer.start(48)
        else:self._animate_window(True)

    def _deferred_top_entry(self):
        if not self.isVisible() or self._motion_exiting:return
        self.move(self._motion_target);self._animate_window(True)

    def hideEvent(self, event):
        if hasattr(self, '_window_motion'):
            self._motion_enter_timer.stop();self._window_motion.stop();self.move(self._motion_target);self._motion_exiting = False
            if QApplication.platformName() not in ('offscreen', 'minimal'):self.setWindowOpacity(1.0)
        super().hideEvent(event)

    def dismiss(self):
        if not self.isVisible() or getattr(self, '_motion_exiting', False):return
        if self._motion_enter_timer.isActive():self._motion_enter_timer.stop();self.hide();return
        self._animate_window(False)


class MotionButton(QPushButton):
    """Native button semantics with interruptible hover and exact 0.96 press feedback."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._press = 1.0;self._hover = 0.0;self.setIconSize(QSize(18,18))
        self._press_animation = QPropertyAnimation(self, b'pressScale', self)
        self._hover_animation = QPropertyAnimation(self, b'hoverAmount', self)
        self.setCursor(Qt.PointingHandCursor)
        self.pressed.connect(lambda:self._tween(self._press_animation, .96, 85))
        self.released.connect(lambda:self._tween(self._press_animation, 1.0, 140))

    def _tween(self, animation, end, ms):
        animation.stop();animation.setDuration(0 if reduced_motion(self.window()) else ms)
        animation.setStartValue(self.property(bytes(animation.propertyName()).decode()))
        animation.setEndValue(end);animation.setEasingCurve(QEasingCurve.OutCubic);animation.start()
    def _set_press(self, value):self._press = value;self.update()
    def _set_hover(self, value):self._hover = value;self.update()
    pressScale = Property(float, lambda self:self._press, _set_press)
    hoverAmount = Property(float, lambda self:self._hover, _set_hover)

    def enterEvent(self, event):self._tween(self._hover_animation, 1.0, 120);super().enterEvent(event)
    def leaveEvent(self, event):self._tween(self._hover_animation, 0.0, 120);super().leaveEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter) and not event.modifiers():self.click();event.accept();return
        super().keyPressEvent(event)
    def _content_rect(self,option):return self.style().subElementRect(QStyle.SE_PushButtonContents,option,self)
    def _paint_label(self,painter,option):
        if self.icon().isNull():self.style().drawControl(QStyle.CE_PushButtonLabel,option,painter,self);return
        rect=self._content_rect(option);has_icon=not self.icon().isNull();gap=7 if has_icon and self.text() else 0
        size=self.iconSize() if has_icon else QSize();width=max(0,rect.width()-size.width()-gap)
        text=self.fontMetrics().elidedText(self.text(),Qt.ElideRight,width);text_width=self.fontMetrics().horizontalAdvance(text)
        left=rect.x()+(rect.width()-size.width()-gap-text_width)//2
        if has_icon:self.icon().paint(painter,left,rect.center().y()-size.height()//2,size.width(),size.height(),Qt.AlignCenter,QIcon.Normal if self.isEnabled() else QIcon.Disabled,QIcon.On if self.isChecked() else QIcon.Off)
        label_rect=rect.adjusted(left-rect.x()+size.width()+gap,0,0,0)
        label=QStyleOptionButton(option);label.rect=label_rect;label.icon=QIcon();label.text=text;self.style().drawControl(QStyle.CE_PushButtonLabel,label,painter,self)
    def paintEvent(self, event):
        p = QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width()/2, self.height()/2);p.scale(self._press,self._press);p.translate(-self.width()/2,-self.height()/2)
        opt = QStyleOptionButton();self.initStyleOption(opt)
        if type(self)._paint_label is MotionButton._paint_label:self.style().drawControl(QStyle.CE_PushButton,opt,p,self)
        else:
            frame=QStyleOptionButton(opt);frame.text='';frame.icon=QIcon();self.style().drawControl(QStyle.CE_PushButton,frame,p,self);self._paint_label(p,opt)
        if self._hover and self.isEnabled():
            p.setPen(Qt.NoPen);p.setBrush(ThemeColor(255,255,255,round(7*self._hover)))
            p.drawRoundedRect(self.rect().adjusted(2,2,-2,-2),9,9)


def reveal_content(widget, duration=140):
    """Only on navigation, never on every search result or live metric refresh."""
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    if not widget or not widget.isVisible() or reduced_motion(widget.window()):return
    effect=getattr(widget,'_reveal_effect',None)
    if effect is None:
        effect=QGraphicsOpacityEffect(widget);widget.setGraphicsEffect(effect);widget._reveal_effect=effect
        widget._reveal_animation=QPropertyAnimation(effect,b'opacity',widget)
    animation=widget._reveal_animation;running=animation.state()==QAbstractAnimation.Running
    animation.stop();animation.setDuration(duration);animation.setStartValue(effect.opacity() if running else .55)
    animation.setEndValue(1.0);animation.setEasingCurve(QEasingCurve.OutCubic);animation.start()
