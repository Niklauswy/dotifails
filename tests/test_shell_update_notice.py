"""Wysun update notice: state parsing (WysunUpdateLogic.js, node) and the bar/popout wiring."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / 'apps/shell'


def js(body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = (SHELL / 'services/WysunUpdateLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class LogicTests(unittest.TestCase):
    def test_parse_valid_state(self):
        out = js('''return parse(JSON.stringify({checked: "2026-11-03T22:00:00Z", source: "/s", branch: "main",
                                       local: "aaa", remote: "bbb", behind: 3, available: true, error: null}))''')
        self.assertEqual(out, {'available': True, 'behind': 3, 'checked': '2026-11-03T22:00:00Z',
                               'branch': 'main', 'error': ''})

    def test_parse_invalid_and_missing_state_is_never_available(self):
        out = js('''return [parse("{not json"), parse("[]"), parse("null"), parse(""), parse(null), parse(undefined)]''')
        broken, empty = out[:3], out[3:]
        for state in broken:
            self.assertFalse(state['available'])
            self.assertTrue(state['error'])
        for state in empty:
            self.assertEqual(state, {'available': False, 'behind': 0, 'checked': '', 'branch': 'main', 'error': ''})

    def test_available_needs_commits_and_no_error(self):
        out = js('''return [parse('{"behind": 0, "available": true}').available,
                           parse('{"behind": 2, "available": true, "error": "sin conexión"}').available,
                           parse('{"behind": 2, "available": false}').available,
                           parse('{"behind": 2, "available": true}').available,
                           parse('{"behind": -2, "available": true}').behind]''')
        self.assertEqual(out, [False, False, False, True, 0])

    def test_changes_plural(self):
        out = js('''return [changes(1, "main"), changes(3, "main"), changes(1, "dev"), changes(0, "main")]''')
        self.assertEqual(out, ['1 cambio nuevo en main', '3 cambios nuevos en main',
                               '1 cambio nuevo en dev', 'No hay cambios nuevos en main'])

    def test_ago(self):
        out = js('''const at = "2026-11-03T22:00:00Z";
                    return [ago(at, Date.parse("2026-11-03T22:00:30Z")), ago(at, Date.parse("2026-11-03T22:03:00Z")),
                            ago(at, Date.parse("2026-11-03T23:05:00Z")), ago(at, Date.parse("2026-11-05T22:00:00Z")),
                            ago(at, Date.parse("2026-11-05T23:00:00Z")), ago("", Date.now()), ago("ayer", Date.now())]''')
        self.assertEqual(out, ['Comprobado hace un momento', 'Comprobado hace 3 min', 'Comprobado hace 1 h 5 min',
                               'Comprobado hace 2 días', 'Comprobado hace 2 días', 'Sin comprobar', 'Sin comprobar'])


class WiringTests(unittest.TestCase):
    def test_bar_icon_opens_the_update_popout(self):
        icons = (SHELL / 'modules/bar/components/StatusIcons.qml').read_text()
        self.assertIn('name: "wysunupdate"', icons)
        self.assertIn('visible: WysunUpdate.available', icons)
        self.assertIn('text: "system_update"', icons)
        content = (SHELL / 'modules/bar/popouts/Content.qml').read_text()
        self.assertIn('name: "wysunupdate"', content)
        self.assertIn('WysunUpdatePopout {}', content)

    def test_service_checks_through_the_cli_and_reads_its_state(self):
        text = (SHELL / 'services/WysunUpdate.qml').read_text()
        self.assertTrue(text.startswith('pragma Singleton'))
        self.assertIn('update.json', text)
        self.assertIn('watchChanges: true', text)
        self.assertIn('["wysun", "update", "--check"]', text)
        self.assertIn('3 * 60 * 1000', text)
        self.assertIn('60 * 60 * 1000', text)
        self.assertIn('Logic.parse(', text)

    def test_apply_opens_a_terminal(self):
        text = (SHELL / 'services/WysunUpdate.qml').read_text()
        self.assertIn('["wysun-terminal", "-e", "wysun", "update"]', text)

    def test_popout_shows_the_update_and_both_actions(self):
        text = (SHELL / 'modules/bar/popouts/WysunUpdatePopout.qml').read_text()
        self.assertIn('"Actualización de Wysun"', text)
        self.assertIn('Logic.changes(WysunUpdate.behind, WysunUpdate.branch)', text)
        self.assertIn('Logic.ago(WysunUpdate.checked, root.now)', text)
        self.assertIn('"Actualizar"', text)
        self.assertIn('"Comprobar ahora"', text)
        self.assertIn('disabled: WysunUpdate.checking', text)
        self.assertIn('WysunUpdate.apply()', text)
        self.assertIn('WysunUpdate.check()', text)


if __name__ == '__main__':
    unittest.main()
