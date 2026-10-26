"""Settings → Wallpaper & style → Design system: Material Design 3 selected, Fluent 2 shown as WIP.

``ProbeTests`` loads the picker in an offscreen Quickshell: point ``WYSUN_TEST_RUNTIME`` at a runtime prefix
(``installer/runtime_build.py --prefix …`` or the installed ``~/.local/share/wysun/runtime``); without it they
are skipped. Nothing is persisted: theme.json keeps only ``{"mode": ...}``.
"""
import json
import os
import re
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_theme_literals import violations  # noqa: E402

SHELL = ROOT / 'apps/shell'
PAGE = SHELL / 'modules/nexus/pages/WallpaperAndStyle.qml'
PICKER = SHELL / 'modules/nexus/common/DesignSystemPicker.qml'


def cards(text):
    """``{system: body}`` for every ``DesignCard { … }`` instance (not the inline component)."""
    found = {}
    for body in re.findall(r'(?m)^    DesignCard \{\n(.*?)\n    \}', text, re.S):
        system = re.search(r'system: "(\w+)"', body).group(1)
        found[system] = body
    return found


class SourceTests(unittest.TestCase):
    def test_page_shows_the_picker_under_its_header(self):
        page = PAGE.read_text()
        header = page.index('Tr.tr("Design system")')
        self.assertLess(page.index('mode: "dark"'), header)
        self.assertLess(header, page.index('DesignSystemPicker {'))
        self.assertLess(page.index('DesignSystemPicker {'), page.index('Tr.tr("Transparency")'))

    def test_picker_declares_material_and_fluent(self):
        found = cards(PICKER.read_text())
        self.assertEqual(sorted(found), ['fluent', 'material'])
        self.assertIn('Tr.tr("Material Design 3")', found['material'])
        self.assertIn('wip: false', found['material'])
        self.assertIn('Tr.tr("Fluent 2")', found['fluent'])
        self.assertIn('wip: true', found['fluent'])
        self.assertIn('readonly property string current: "material"', PICKER.read_text())

    def test_wip_card_is_disabled_and_marked(self):
        text = PICKER.read_text()
        self.assertRegex(text, r'readonly property bool selected: !wip && root\.current === system')
        self.assertRegex(text, r'StateLayer \{[^}]*visible: !card\.wip[^}]*disabled: card\.wip', 'WIP card takes no clicks')
        self.assertRegex(text, r'Chip \{[^}]*visible: card\.wip[^}]*Tr\.tr\("WIP"\)')
        self.assertIn('Qt.ForbiddenCursor', text)

    def test_previews_use_the_palette_and_shape_tokens(self):
        text = PICKER.read_text()
        self.assertEqual(violations(text.splitlines()), [])
        self.assertEqual(violations(PAGE.read_text().splitlines()), [])
        self.assertNotRegex(text, r'radius: \d', 'radii come from Tokens.rounding')
        self.assertNotRegex(text, r'duration: \d', 'durations come from Anim / Tokens.anim')
        self.assertIn('MaterialShape', text)
        self.assertIn('Tokens.rounding.extraSmall', text)  # Fluent's contained corners

    def test_nothing_new_is_persisted(self):
        self.assertNotIn('theme.json', PICKER.read_text().replace('theme.json keeps only', ''))
        self.assertNotIn('setMode', PICKER.read_text())


@unittest.skipUnless(os.environ.get('WYSUN_TEST_RUNTIME'), 'WYSUN_TEST_RUNTIME (runtime prefix) not set')
class ProbeTests(unittest.TestCase):
    def probe(self, mode):
        runtime = Path(os.environ['WYSUN_TEST_RUNTIME']).expanduser()
        with tempfile.TemporaryDirectory(prefix='wysun-design-') as tmp:
            home = Path(tmp)
            shell = home / 'shell'
            (shell / 'services').mkdir(parents=True)
            (shell / 'services/Colours.qml').symlink_to(SHELL / 'services/Colours.qml')
            (shell / 'services/Wallpapers.qml').write_text(
                'pragma Singleton\nimport Quickshell\nSingleton { property string current: "" }\n')
            for sub in ('utils', 'components'):
                (shell / sub).symlink_to(SHELL / sub)
            (shell / 'modules/nexus/common').mkdir(parents=True)
            (shell / 'modules/nexus/common/DesignSystemPicker.qml').symlink_to(PICKER)
            (shell / 'shell.qml').write_text((ROOT / 'tests/shell_design_system_probe.qml').read_text())
            env = dict(os.environ, HOME=tmp, QT_QPA_PLATFORM='offscreen', WAYLAND_DISPLAY='',
                       HYPRLAND_INSTANCE_SIGNATURE='', WYSUN_LIB_DIR=str(runtime / 'shell/lib/wysun'),
                       QML_IMPORT_PATH=os.pathsep.join([str(runtime / 'shell/lib/qt6/qml'),
                                                        str(runtime / 'deps/lib/qt6/qml')]))
            for key, sub in (('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_STATE_HOME', 'state'),
                             ('XDG_CACHE_HOME', 'cache'), ('XDG_RUNTIME_DIR', 'run')):
                (home / sub).mkdir(mode=0o700)
                env[key] = str(home / sub)
            env['XDG_DATA_DIRS'] = str(home / 'none')
            (home / 'data/wysun/theme').mkdir(parents=True)
            (home / 'data/wysun/theme/tokens.json').write_text((ROOT / 'apps/python/wysun_core/tokens.json').read_text())
            (home / 'config/wysun').mkdir(parents=True)
            (home / 'config/wysun/theme.json').write_text(json.dumps({'mode': mode}))
            result = subprocess.run([str(runtime / 'quickshell/bin/quickshell'), '-p', str(shell)], env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, cwd=tmp)
            theme = json.loads((home / 'config/wysun/theme.json').read_text())
        line = next((l for l in result.stdout.splitlines() if 'DESIGN ' in l), None)
        self.assertIsNotNone(line, result.stdout)
        problems = [l for l in result.stdout.splitlines() if re.search(r'DesignSystemPicker\.qml.*(TypeError|ReferenceError|Unable|error)', l, re.I)]
        self.assertEqual(problems, [])
        return json.loads(line.split('DESIGN ', 1)[1]), theme

    def test_material_selected_fluent_wip_in_both_modes(self):
        for mode in ('light', 'dark'):
            with self.subTest(mode=mode):
                values, theme = self.probe(mode)
                self.assertEqual(values['current'], 'material')
                self.assertEqual(values['columns'], 2)
                by_system = {card['system']: card for card in values['cards']}
                self.assertEqual(sorted(by_system), ['fluent', 'material'])
                self.assertEqual(by_system['material']['name'], 'Material Design 3')
                self.assertTrue(by_system['material']['selected'])
                self.assertTrue(by_system['material']['interactive'])
                self.assertEqual(by_system['fluent']['name'], 'Fluent 2')
                self.assertTrue(by_system['fluent']['wip'])
                self.assertFalse(by_system['fluent']['selected'])
                self.assertFalse(by_system['fluent']['interactive'])
                self.assertEqual(theme, {'mode': mode})


if __name__ == '__main__':
    unittest.main()
