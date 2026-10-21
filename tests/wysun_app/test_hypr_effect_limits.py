"""Native effect bounds from Hyprland v0.55.2 ConfigValues.cpp, no host bus."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
from hypr_settings import effects_script


class EffectBoundsTests(unittest.TestCase):
    def test_native_rounding_limit_is_20_not_picom_30(self):
        values={'corner-radius':20,'shadow':True,'shadow-radius':18,
                'shadow-opacity':.25,'blur-background':True,'blur-strength':3,
                'duration':120,'fading':True}
        self.assertIn('["rounding"] = 20',effects_script(values))
        for radius in (21,30):
            with self.subTest(radius=radius),self.assertRaisesRegex(ValueError,'corner-radius'):
                effects_script(dict(values,**{'corner-radius':radius}))


if __name__=='__main__':unittest.main()
