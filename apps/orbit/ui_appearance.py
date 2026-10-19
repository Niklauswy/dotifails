"""Small, local appearance preferences; no desktop or compositor ownership."""
import json
import os
import time
from pathlib import Path

DEFAULTS={'opacity':80,'reduced_motion':False}
_cache={}


def preference_path(home=None):
    from hypr_settings import config_dir
    root=config_dir(home)
    return root/'orbit/appearance.json'


def read_appearance(home=None):
    path=preference_path(home);now=time.monotonic();cached=_cache.get(path)
    if cached and now-cached[0]<.5:return dict(cached[1])
    values=dict(DEFAULTS)
    try:
        data=json.loads(path.read_text())
        if isinstance(data,dict):
            opacity=data.get('opacity',80)
            if isinstance(opacity,(float,int)):values['opacity']=max(65,min(100,round(opacity)))
            values['reduced_motion']=data.get('reduced_motion') is True
    except (OSError,ValueError,TypeError,OverflowError):pass
    _cache[path]=(now,values);return dict(values)


def save_appearance(values,home=None):
    path=preference_path(home);data={}
    if path.exists():
        data=json.loads(path.read_text())
        if not isinstance(data,dict):raise ValueError('El archivo de apariencia no contiene un objeto JSON.')
    data.update(opacity=max(65,min(100,int(values['opacity']))),reduced_motion=bool(values['reduced_motion']))
    path.parent.mkdir(parents=True,exist_ok=True)
    import tempfile
    fd,name=tempfile.mkstemp(prefix='.appearance-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n')
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)
    _cache.pop(path,None)
