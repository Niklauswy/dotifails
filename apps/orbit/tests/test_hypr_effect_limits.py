"""Native effect bounds from Hyprland v0.55.2 ConfigValues.cpp, no host bus."""
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
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

    def test_native_ui_bound_and_x11_bound_are_separate(self):
        # Build only the effect form; no SettingsHub startup, jobs, network or IPC.
        from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QFormLayout
        from settings_hub import SettingsHub
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as home:
            for native,maximum in ((True,20),(False,30)):
                with self.subTest(native=native),patch('desktop_backend.wayland',return_value=native):
                    widget=QWidget();layout=QVBoxLayout(widget);form=QFormLayout();layout.addLayout(form)
                    owner=SimpleNamespace(env=SimpleNamespace(home=Path(home),component_values=lambda _:{}),
                        component_controls={},page=lambda:layout,page_heading=lambda *_:None,
                        scroll_form=lambda _:form,choose_color=lambda _:None)
                    SettingsHub.build_component(owner,'effects')
                    control=owner.component_controls['effects']['corner-radius']
                    self.assertEqual(control.maximum(),maximum)
                    control.setValue(30)
                    self.assertEqual(control.value(),maximum)
                    widget.close();widget.deleteLater();app.processEvents()


if __name__=='__main__':unittest.main()
