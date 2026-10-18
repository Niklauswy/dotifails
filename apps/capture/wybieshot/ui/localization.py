"""Spanish Qt labels for this screenshot process, with a bounded color fallback."""
from pathlib import Path
from PySide6.QtCore import QLibraryInfo,QTranslator,QCoreApplication
from PySide6.QtWidgets import QLabel,QPushButton


def install_translations(app):
    if hasattr(app,'_wybieshot_translation'):return app._wybieshot_translation is not None
    translator=QTranslator(app)
    candidates=[Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath))/'qtbase_es.qm',Path('/usr/share/qt6/translations/qtbase_es.qm')]
    for path in candidates:
        if translator.load(str(path)):
            app.installTranslator(translator);app._wybieshot_translation=translator;return True
    app._wybieshot_translation=None;return False


def prepare_color_picker(picker):
    # Keep a complete local palette/HTML editor; screen sampling would read the
    # dimmed overlay rather than the frozen source, so that action is unavailable.
    screen=QCoreApplication.translate('QColorDialog','&Pick Screen Color')
    fallback={'&Basic colors':'Colores básicos','&Custom colors':'Colores personalizados',
              'Hu&e:':'Tono:','&Sat:':'Saturación:','&Val:':'Brillo:',
              '&Red:':'Rojo:','&Green:':'Verde:','Bl&ue:':'Azul:',
              'A&lpha channel:':'Canal alfa:','&HTML:':'HTML:',
              '&Add to Custom Colors':'Añadir a colores personalizados','OK':'Aceptar','Cancel':'Cancelar'}
    for control in picker.findChildren(QLabel)+picker.findChildren(QPushButton):
        text=control.text()
        if isinstance(control,QPushButton) and text in ('&Pick Screen Color',screen):
            control.setObjectName('wybieUnsupportedScreenPicker');control.setEnabled(False);control.hide()
        elif text in fallback:control.setText(fallback[text])
