"""Where recordings are saved: the video folder, the private project folders inside it, and the preferences."""
import json
from pathlib import Path

from wysun_core import paths
from wysun_core.jsonio import atomic_write_json
from .library import Library


def preferences_path():return paths.config('wysun', 'recorder', 'preferences.json')
def preferences():
    try:data=json.loads(preferences_path().read_text())
    except (OSError,ValueError):return {}
    return data if isinstance(data,dict) else {}
def save_preferences(**values):
    current=preferences();current.update(values);atomic_write_json(preferences_path(),current)
def videos_root():return Path(preferences().get('videos_folder',str(Path.home()/'Videos'))).expanduser()


class VideoLibrary(Library):
    def __init__(self,folder=None):
        self.videos=Path(folder) if folder else videos_root();self.videos.mkdir(parents=True,exist_ok=True)
        super().__init__(self.videos/'.wybie/recordings')
