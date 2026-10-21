# Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
# Fuente: 507d66285e9d9fde9330adc64159cfdebb28c19a; véase THIRD_PARTY.md.
# Los QML de origen no incluyen avisos de copyright adicionales por archivo.
"""Wysun Power: machine status and session controls."""
from theme_tokens import apply_style

import time
from PySide6.QtCore import Qt,QTimer,QEvent,QDateTime,QLocale
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QWidget,QFrame,QProgressBar
from utility_material import MaterialSurface as Surface, surface, metrics
from desktop_common import text_label

class PowerWindow(Surface):
    def __init__(self,owner):
        super().__init__('Wysun Power','Estado del equipo y controles de sesión',960,650);self.owner=owner;self.action_buttons=[]
        from power_widgets import BatteryGauge,SessionAction
        gap=metrics()['gap']
        workspace=QHBoxLayout();workspace.setContentsMargins(0,0,0,0);workspace.setSpacing(gap);self.workspace=QWidget();self.workspace.setLayout(workspace)
        overview=surface(QWidget());overview_layout=QVBoxLayout(overview);overview_layout.setContentsMargins(gap,gap,gap,gap);overview_layout.setSpacing(gap)
        controls=surface(QWidget(), 'navigation');controls_layout=QVBoxLayout(controls);controls_layout.setContentsMargins(gap,gap,gap,gap);controls_layout.setSpacing(gap)
        workspace.addWidget(overview,1);workspace.addWidget(controls,1);self.outer.addWidget(self.workspace,1)
        overview_layout.addWidget(text_label('Estado del equipo','sectionLabel'))
        hero=QHBoxLayout();hero.setSpacing(20)
        self.clock_label=text_label('');apply_style(self.clock_label,'font-size:68px;font-weight:500;letter-spacing:-3px;color:@text_strong;');self.clock_label.setWordWrap(False);hero.addWidget(self.clock_label)
        self.date_label=text_label('');self.date_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter);apply_style(self.date_label,'color:@glyph_muted;font-size:@font_body;');hero.addWidget(self.date_label,1);overview_layout.addLayout(hero)
        card=QFrame();card.setObjectName('batteryCard');apply_style(card,'QFrame#batteryCard{background:@card;border:@border solid @card_line;border-radius:@radius_l;}')
        energy=QHBoxLayout(card);energy.setContentsMargins(14,14,22,14);energy.setSpacing(18)
        self.gauge=BatteryGauge();energy.addWidget(self.gauge)
        details=QVBoxLayout();details.setSpacing(5)
        top=QHBoxLayout();self.battery_label=text_label('');apply_style(self.battery_label,'font-size:34px;font-weight:600;color:@text;');top.addWidget(self.battery_label)
        title=text_label('BATERÍA','eyebrow');top.addWidget(title,1,Qt.AlignRight);details.addLayout(top)
        self.battery_status=text_label('');details.addWidget(self.battery_status)
        self.estimate=text_label('','subtitle');details.addWidget(self.estimate)
        self.health=text_label('','subtitle');apply_style(self.health,'font-size:11px;color:@section;');details.addWidget(self.health)
        energy.addLayout(details,1);overview_layout.addWidget(card);overview_layout.addStretch()
        self.battery_bar=QProgressBar(self);self.battery_bar.setRange(0,100);self.battery_bar.hide()
        controls_layout.addWidget(text_label('Controles de sesión','title'))
        from system_panels import power_rows
        actions=power_rows();primary=QVBoxLayout();primary.setSpacing(metrics()['space_s']);secondary=QVBoxLayout();secondary.setSpacing(metrics()['space_s'])
        hints=['Mantén tus aplicaciones abiertas','Continúa justo donde estabas','Volver al inicio de sesión','Reiniciar el equipo','Apagar el equipo']
        for i,action in enumerate(actions):
            title='Bloquear' if i==0 else action['title']
            b=SessionAction(title,hints[i],action['action'],danger=i==4,compact=i>=2)
            b.clicked.connect(lambda checked=False,r=action:self.trigger(r));b.installEventFilter(self);self.action_buttons.append(b)
            (primary if i<2 else secondary).addWidget(b,1)
        controls_layout.addLayout(primary);controls_layout.addLayout(secondary);controls_layout.addStretch()
        footer=QHBoxLayout();self.uptime_label=text_label('','subtitle');apply_style(self.uptime_label,'color:@section;font-size:11px;');footer.addWidget(self.uptime_label,1)
        hint=text_label('Flechas · Enter · Esc','subtitle');apply_style(hint,'font-size:10px;color:@section;');footer.addWidget(hint);self.outer.addLayout(footer)
        self.clock_timer=QTimer(self);self.clock_timer.setInterval(1000);self.clock_timer.timeout.connect(self.update_clock)
    @staticmethod
    def uptime_text(seconds):
        minutes=max(0,int(seconds)//60);days,minutes=divmod(minutes,1440);hours,minutes=divmod(minutes,60)
        parts=[]
        if days:parts.append(f'{days} d')
        if hours:parts.append(f'{hours} h')
        if minutes or parts:parts.append(f'{minutes} min')
        return 'Encendido hace '+(' '.join(parts) if parts else 'menos de 1 min')
    @staticmethod
    def battery_data():
        from energy_data import battery_snapshot
        data=battery_snapshot();return data['capacity'],data['status']
    @staticmethod
    def battery_text():
        capacity,_=PowerWindow.battery_data()
        return f'Batería: {capacity}%' if capacity is not None else 'Batería: sin dato'
    def update_clock(self):
        now=QDateTime.currentDateTime();locale=QLocale('es_MX')
        self.clock_label.setText(now.toString('HH:mm'))
        self.date_label.setText(locale.toString(now,'dddd').capitalize()+'\n'+locale.toString(now,"d 'de' MMMM 'de' yyyy"))
        self.uptime_label.setText(self.uptime_text(time.clock_gettime(time.CLOCK_BOOTTIME)))
        from energy_data import battery_snapshot,time_estimate
        data=battery_snapshot();capacity,status=data['capacity'],data['status']
        self.battery_label.setText(f'{capacity}%' if capacity is not None else '—')
        self.battery_bar.setValue(capacity if capacity is not None else 0);self.gauge.set_value(capacity,status=='Charging')
        statuses={'Charging':'Conectado · cargando','Discharging':'Usando la batería','Full':'Carga completa','Not charging':'Conectado · sin cargar','Unknown':'Estado no disponible'}
        self.battery_status.setText('Batería no disponible' if capacity is None else 'Batería baja · conecta el cargador' if capacity<=20 and status=='Discharging' else statuses.get(status,'Estado no disponible'))
        apply_style(self.battery_status,'color:@warning;' if capacity is not None and capacity<=20 and status=='Discharging' else 'color:@accent;')
        self.estimate.setText(time_estimate(data['hours'],status=='Charging') if capacity is not None else 'Este equipo no reporta una batería')
        specs=[]
        if data['watts'] is not None:specs.append(f"{data['watts']:.1f} W")
        if data['health'] is not None:specs.append(f"Salud {data['health']:.0f}%")
        if data['cycles'] is not None:specs.append(f"{int(data['cycles'])} ciclos")
        self.health.setText('  ·  '.join(specs));self.health.setVisible(bool(specs))
    def showEvent(self,event):
        self.update_clock();self.clock_timer.start();super().showEvent(event)
    def hideEvent(self,event):
        self.clock_timer.stop();super().hideEvent(event)
    def present(self):
        super().present();self.action_buttons[0].setFocus(Qt.OtherFocusReason)
    def eventFilter(self,obj,event):
        if obj in self.action_buttons and event.type()==QEvent.KeyPress:
            key=event.key()
            if key in (Qt.Key_Return,Qt.Key_Enter):
                if not event.isAutoRepeat() and obj.isEnabled():obj.click()
                return True
            if key in (Qt.Key_Left,Qt.Key_Up,Qt.Key_Right,Qt.Key_Down):
                step=-1 if key in (Qt.Key_Left,Qt.Key_Up) else 1
                self.action_buttons[(self.action_buttons.index(obj)+step)%len(self.action_buttons)].setFocus(Qt.OtherFocusReason)
                return True
        return super().eventFilter(obj,event)
    def trigger(self,row):
        if self.owner.power_action(row):self.hide()
