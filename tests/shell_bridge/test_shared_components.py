"""Shell surfaces share one overlay window and one definition of each common control."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / 'apps/shell'


def qml(relative):
    return (SHELL / relative).read_text()


def qml_files():
    return sorted(p for p in SHELL.rglob('*.qml') if 'plugin' not in p.relative_to(SHELL).parts)


def relative(paths):
    return sorted(str(p.relative_to(SHELL)) for p in paths)


def inline(name):
    return relative(p for p in qml_files() if re.search(rf'(?m)^\s*component\s+{name}\s*:', p.read_text()))


def named(name):
    return relative(p for p in qml_files() if p.stem == name)


class OverlayWindowTests(unittest.TestCase):
    maxDiff = 2000
    OVERLAYS = ['modules/launcher/Launcher.qml', 'modules/launcher/EmojiPicker.qml',
                'modules/cheatsheet/Cheatsheet.qml', 'modules/wallpaperpicker/WallpaperPicker.qml',
                'modules/colors/ColorWindow.qml']

    def test_overlay_window_owns_the_pattern(self):
        text = qml('components/OverlayWindow.qml')
        for needle in ('HyprlandFocusGrab', 'WlrKeyboardFocus.OnDemand', 'WlrLayer.Overlay',
                       'sequence: "Escape"', 'required property ShellScreen modelData', 'ShellState.forScreen'):
            self.assertIn(needle, text)

    def test_overlays_use_overlay_window(self):
        for rel in self.OVERLAYS:
            text = qml(rel)
            self.assertRegex(text, r'\bOverlayWindow\s*\{', rel)
            for copy in ('HyprlandFocusGrab', 'WlrKeyboardFocus.OnDemand', 'WlrLayer.Overlay'):
                self.assertNotIn(copy, text, rel)

    # Surfaces that grab focus but are not overlays: the drawers share one window per screen whose
    # keyboard focus depends on which drawer is open, and the bar popouts live inside the bar window.
    NOT_OVERLAYS = ['modules/bar/popouts/Wrapper.qml', 'modules/drawers/ContentWindow.qml']

    def test_no_other_module_copies_the_overlay_pattern(self):
        found = [p for p in qml_files() if 'HyprlandFocusGrab' in p.read_text() and 'WlrKeyboardFocus.OnDemand' in p.read_text()]
        self.assertEqual(relative(found), sorted(['components/OverlayWindow.qml'] + self.NOT_OVERLAYS))

    def test_process_window_is_a_regular_window(self):
        # Documented exception: a resizable toplevel with a title and minimum size, not an overlay.
        self.assertRegex(qml('modules/processes/ProcessWindow.qml'), r'(?m)^FloatingWindow\s*\{')

    def test_launcher_keeps_its_own_escape(self):
        # Escape closes the action menu, the expanded preview or a stacked folder before the launcher.
        self.assertIn('closeOnEscape: false', qml('modules/launcher/Launcher.qml'))

    def test_color_window_survives_sampling(self):
        text = qml('modules/colors/ColorWindow.qml')
        self.assertRegex(text, r'focusGrab:[^\n]*!\s*win\.sampling')
        self.assertIn('closeOnEscape: false', text)


class SearchFieldTests(unittest.TestCase):
    def test_search_fields_use_search_bar(self):
        for rel in ('modules/wallpaperpicker/WallpaperPicker.qml', 'modules/launcher/LauncherPanel.qml'):
            text = qml(rel)
            self.assertRegex(text, r'\bSearchBar\s*\{', rel)
            self.assertNotRegex(text, r'\b(TextInput|TextFieldBase)\s*\{', rel)

    def test_only_the_lock_screen_uses_a_raw_text_field_in_modules(self):
        raw = [p for p in qml_files() if p.relative_to(SHELL).parts[0] == 'modules'
               and re.search(r'\b(TextInput|TextFieldBase)\s*\{', p.read_text())]
        self.assertEqual(relative(raw), ['modules/lockscreen/LockScene.qml'])  # a password, not a search

    def test_wallpaper_filter_keeps_carousel_keys(self):
        text = qml('modules/wallpaperpicker/WallpaperPicker.qml')
        block = text[text.index('SearchBar {'):]
        self.assertIn('Keys.priority: Keys.BeforeItem', block)
        self.assertIn('carousel.random()', block)

    def test_search_bar_has_a_bare_variant(self):
        text = qml('components/controls/SearchBar.qml')
        self.assertIn('property bool bare', text)
        self.assertIn('bare: true', qml('modules/launcher/LauncherPanel.qml'))


class SingleDefinitionTests(unittest.TestCase):
    def test_no_inline_toggle(self):
        self.assertEqual(inline('Toggle'), [])
        self.assertEqual(named('SwitchRow'), ['components/controls/SwitchRow.qml'])
        self.assertEqual(named('ToggleTile'), ['components/controls/ToggleTile.qml'])

    def test_one_chip(self):
        self.assertEqual(inline('Chip'), [])
        self.assertEqual(named('Chip'), ['components/Chip.qml'])
        self.assertNotRegex(qml('components/Chip.qml'), r'duration:\s*\d')
        self.assertRegex(qml('modules/launcher/TranslateCard.qml'), r'\bChip\s*\{')

    def test_tabs_are_not_redefined(self):
        self.assertEqual(inline('Tab'), ['modules/dashboard/Tabs.qml'])  # the dashboard's underline tab bar
        self.assertEqual(named('Segmented'), ['components/controls/Segmented.qml'])


if __name__ == '__main__':
    unittest.main()
