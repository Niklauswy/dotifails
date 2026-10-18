"""Short, interruptible state transitions; no repeating recording animations."""
import os,json
from pathlib import Path
from PySide6.QtWidgets import QApplication,QStyle

def reduced_motion():
    if any(os.environ.get(key,'').lower() in ('1','true','yes') for key in ('LOOMREC_REDUCED_MOTION','ORBIT_REDUCED_MOTION')):return True
    try:
        path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'loomrec/appearance.json'
        if json.loads(path.read_text()).get('reduced_motion'):return True
    except (OSError,ValueError,AttributeError):pass
    try:
        path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'orbit/appearance.json'
        if json.loads(path.read_text()).get('reduced_motion'):return True
    except (OSError,ValueError,AttributeError):pass
    app=QApplication.instance()
    return bool(app and app.style().styleHint(QStyle.SH_Widget_Animation_Duration)==0)
