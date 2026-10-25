import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'apps/wysun'))
from environment_settings import EnvironmentSettings
import theme_core


class ThemeTests(unittest.TestCase):
    def test_wallpaper_defaults_to_the_shipped_one_and_respects_personal_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);config=home/'.config/orbit';config.mkdir(parents=True)
            images=home/'.local/share/backgrounds';images.mkdir(parents=True)
            name=theme_core.default_wallpaper()
            self.assertEqual(env_default(home),'','without the shipped file there is no default wallpaper')
            (images/name).write_bytes(b'fixture')
            for mode in ('auto','light','dark'):
                (config/'theme.json').write_text(json.dumps(dict(mode=mode)))
                from theme_tokens import invalidate
                invalidate()
                self.assertEqual(env_default(home),str(images/name),'the wallpaper does not depend on the mode')
            env=EnvironmentSettings(home)
            env.save_section('wallpaper',dict(default='/custom/personal.jpg'))
            self.assertEqual(env.wallpaper_values()['default'],'/custom/personal.jpg')

    def test_only_the_shipped_wallpaper_is_in_the_distribution(self):
        root=Path(__file__).parents[1]
        manifest=json.loads((root/'manifests/themes.json').read_text())
        self.assertEqual(list(manifest),['material-you'])
        self.assertEqual([p.name for p in (root/'assets/backgrounds').iterdir()],[manifest['material-you']['wallpaper']])
        self.assertFalse((root/'assets/appearance').exists(),'there are no per-theme packs any more')


def env_default(home):
    return EnvironmentSettings(home).wallpaper_values().get('default','')
