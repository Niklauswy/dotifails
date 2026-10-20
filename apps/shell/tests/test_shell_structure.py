from pathlib import Path
import unittest

SHELL = Path(__file__).resolve().parents[1]
REPO = SHELL.parents[1]


class ShellStructureTests(unittest.TestCase):
    def test_legacy_top_bar_and_centre_popup_are_removed_from_shell(self):
        self.assertFalse((SHELL / "Bar.qml").exists())
        self.assertFalse((SHELL / "Surface.qml").exists())
        root = (SHELL / "shell.qml").read_text()
        self.assertIn("RailModule.Rail", root)
        self.assertIn("FrameModule.ScreenFrame", root)
        self.assertIn("PopoutModule.PopoutHost", root)
        self.assertNotIn('"Centro de escritorio"', root)

    def test_frame_is_passive_and_hidden_on_local_fullscreen(self):
        frame = (SHELL / "modules/frame/ScreenFrame.qml").read_text()
        self.assertIn("mask: Region {}", frame)
        self.assertIn("!fullscreen", frame)
        self.assertIn('namespace: "wysun-frame"', frame)
        self.assertIn('"wysun-rail"', (SHELL / "modules/rail/Rail.qml").read_text())

    def test_popout_has_escape_outside_click_and_reduced_motion_geometry(self):
        popout = (SHELL / "modules/popouts/PopoutHost.qml").read_text()
        self.assertIn('sequence: "Escape"', popout)
        self.assertIn("onClicked: host.controller.close()", popout)
        self.assertIn("progress = targetVisible ? 1 : 0;", popout)
        self.assertIn('progress >= 1', popout)
        self.assertIn('progress <= 0', popout)
        self.assertIn("host.motion.reducedMotion ? 1 : host.progress", popout)
        self.assertIn('namespace: "wysun-popout"', popout)
        state = (SHELL / "ShellState.qml").read_text()
        self.assertIn("returnFocusItem", state)
        self.assertIn("forceActiveFocus()", state)

    def test_scheme_consumer_uses_xdg_state_and_fallback_theme(self):
        colours = (SHELL / "services/Colours.qml").read_text()
        self.assertIn('Quickshell.env("XDG_STATE_HOME")', colours)
        self.assertIn('"/wysun/scheme.json"', colours)
        self.assertIn("Appearance.applyScheme(roles, mode, false)", colours)
        self.assertIn("Appearance.applyScheme(roles, mode, true)", colours)

    def test_caelestia_shell_layers_have_utils_and_config_modules(self):
        self.assertTrue((SHELL / "utils/PopoutGeometry.js").is_file())
        self.assertTrue((SHELL / "config/Paths.js").is_file())
        self.assertIn('"../../utils/PopoutGeometry.js"', (SHELL / "modules/popouts/PopoutHost.qml").read_text())

    def test_fonts_and_licenses_are_packaged(self):
        material_symbols = SHELL / "assets/fonts/MaterialSymbolsRounded.ttf"
        self.assertTrue(material_symbols.is_file())
        self.assertLessEqual(material_symbols.stat().st_size, 64 * 1024)
        self.assertTrue((SHELL / "assets/fonts/Rubik-Variable.ttf").is_file())
        self.assertTrue((REPO / "LICENSES/Apache-2.0.txt").is_file())
        self.assertTrue((REPO / "LICENSES/OFL-Rubik.txt").is_file())
        self.assertTrue((REPO / "LICENSES/GPL-3.0.txt").is_file())

    def test_super_l_remains_the_emoji_shortcut(self):
        config = (REPO / "config/.config/wysun/hyprland.lua").read_text()
        self.assertIn('hl.bind("SUPER + L", hl.dsp.exec_cmd("wysun emoji")', config)


if __name__ == "__main__":
    unittest.main()
