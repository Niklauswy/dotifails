"""Read-only adapters to Wysun Recorder's shared design language."""
from PySide6.QtCore import QSize, Qt
from loomrec.ui.components import SoftButton, label, SpinBox, ComboBox
from loomrec.ui.materials import apply_material
from loomrec.ui.tokens import apply_theme as recorder_theme, apply_style, color, tokens
from .localization import install_translations
from .icons import icon


def button(text, callback=None, symbol=None, primary=False, compact=False):
    control=SoftButton(text,primary=primary,quiet=compact)
    if symbol:control.setIcon(icon(symbol,'on_accent' if primary else 'muted'))
    control.setMinimumHeight(40)
    if compact:control.setFixedWidth(40)
    if callback:control.clicked.connect(callback)
    return control


def tool_button(name, symbol, shortcut, callback):
    control=button('',callback,symbol,compact=True)
    control.setCheckable(True);control.setAccessibleName(name)
    control.setToolTip(f'{name} · {shortcut}');control.setIconSize(QSize(22,22))
    return control


def localize_buttons(box, accept='Aceptar'):
    from PySide6.QtWidgets import QDialogButtonBox
    from PySide6.QtGui import QIcon
    for standard,text in ((QDialogButtonBox.Ok,accept),(QDialogButtonBox.Save,'Guardar'),(QDialogButtonBox.Cancel,'Cancelar')):
        control=box.button(standard)
        if control:control.setText(text);control.setIcon(QIcon());control.setAccessibleName(text)
    return box


def apply_theme(app):
    install_translations(app)
    recorder_theme(app)
