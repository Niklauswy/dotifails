import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'apps/wysun'))
from environment_settings import EnvironmentSettings


class ThemeTests(unittest.TestCase):
    def test_wallpaper_follows_profile_and_respects_personal_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);config=home/'.config/orbit';config.mkdir(parents=True)
            images=home/'.local/share/backgrounds';images.mkdir(parents=True)
            for name in ('azul.jpg','tokyo.png'):(images/name).write_bytes(b'fixture')
            for name,key in (('azul.jpg','severance'),('tokyo.png','tokyo')):
                (config/'theme.json').write_text(json.dumps(dict(id=key)))
                from theme_tokens import invalidate
                invalidate()
                env=EnvironmentSettings(home)
                self.assertEqual(env.wallpaper_values()['default'],str(images/name))
            env.save_section('wallpaper',dict(default='/custom/personal.jpg'))
            self.assertEqual(env.wallpaper_values()['default'],'/custom/personal.jpg')
