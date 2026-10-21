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

    def test_effect_form_uses_hyprland_bounds_including_under_xwayland(self):
        # The shell form is generated from the bridge schema; its limits must match Hyprland's.
        import os
        os.environ['WYSUN_APP_DIR']=str(Path(__file__).resolve().parents[2]/'apps/wysun')
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'apps/shell/wysun'))
        import desktop_bridge
        rows={row[0]:row for row in desktop_bridge.COMPONENTS['effects'][2]}
        self.assertEqual(rows['corner-radius'][3:5],(0,20))
        for key in ('shadow','blur-background','fading'):self.assertEqual(rows[key][2],'bool')
        self.assertEqual(rows['vsync'][2],'fixed')


if __name__=='__main__':unittest.main()
