"""The shell reads apps/wysun/wysun_core/tokens.json; tokens.hpp and appearanceconfig.hpp are only its fallback.

``test_plugin_reads_tokens_json`` runs the built plugin: point ``WYSUN_TEST_RUNTIME`` at a runtime prefix
built from this tree (``installer/runtime_build.py --prefix …``); without it the test is skipped.
"""
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'apps/shell/plugin/src/Wysun/Config'
TOKENS = ROOT / 'apps/wysun/wysun_core/tokens.json'
sys.path.insert(0, str(ROOT / 'installer'))
import wayland  # noqa: E402

INT_MAX = 2147483647
WEIGHTS = {'QFont::Normal': 400, 'QFont::Medium': 500}


def tokens():
    return json.loads(TOKENS.read_text())


def node(source, name):
    """Body of ``class <name> : public settings::ObjectNode { … };`` in a header."""
    match = re.search(r'class %s\b[^{]*\{(.*?)\n\};' % name, source, re.S)
    if not match:
        raise AssertionError('no class ' + name)
    return match.group(1)


def number(text):
    text = text.strip()
    if text == 'std::numeric_limits<int>::max()':
        return INT_MAX
    if '/' in text:
        top, bottom = text.split('/')
        return float(Fraction(top.strip()) / Fraction(bottom.strip()))
    return float(text) if '.' in text else int(text)


def int_properties(body):
    return {name: number(value) for name, value in
            re.findall(r'CONFIG_(?:GLOBAL_)?PROPERTY\(int, (\w+), ([^)]+\)?)\)', body)}


def curves(body):
    return {name: [number(v) for v in values.split(',')] for name, values in
            re.findall(r'CONFIG_GLOBAL_PROPERTY\(QList<qreal>,\s*(\w+),\s*DEFAULT_ARG\(\{([^}]*)\}\)\)', body)}


def font_styles(source):
    styles = {}
    for name, family, body in re.findall(r'FONT_STYLE\((\w+), u"([^"]+)"_s,(.*?)\n\)', source, re.S):
        sizes = []
        for spec in re.findall(r'FONT\(\{([^}]*(?:\{\})?[^}]*)\}\)', body):
            size = int(re.search(r'\.size = (\d+)', spec).group(1))
            weight = re.search(r'\.weight = (QFont::\w+)', spec)
            sizes.append({'size': size, 'weight': WEIGHTS[weight.group(1) if weight else 'QFont::Normal']})
        styles[name.lower()] = {'family': family, 'sizes': dict(zip(('large', 'medium', 'small'), sizes))}
    return styles


class FallbackParityTests(unittest.TestCase):
    def test_tokens_hpp_fallback_matches_json(self):
        source = (CONFIG / 'tokens.hpp').read_text()
        data = tokens()
        for group, cls in (('rounding', 'RoundingTokens'), ('spacing', 'SpacingTokens'), ('padding', 'PaddingTokens')):
            with self.subTest(group=group):
                self.assertEqual(int_properties(node(source, cls)), data[group])
        self.assertEqual(int_properties(node(source, 'AnimDurationTokens')), data['anim']['durations'])
        fallback = curves(node(source, 'AnimCurves'))
        self.assertEqual(set(fallback), set(data['anim']['curves']))
        for name, points in data['anim']['curves'].items():
            with self.subTest(curve=name):
                self.assertEqual(len(fallback[name]), len(points))
                for ours, theirs in zip(fallback[name], points):
                    self.assertAlmostEqual(ours, theirs, places=12)

    def test_type_scale_matches_json(self):
        styles = font_styles((CONFIG / 'appearanceconfig.hpp').read_text())
        font = tokens()['font']
        self.assertEqual(set(styles), {'headline', 'title', 'body', 'label', 'mono'})
        for role, style in styles.items():
            with self.subTest(role=role):
                self.assertEqual(style['family'], font['family']['mono' if role == 'mono' else 'sans'])
                self.assertEqual(style['sizes'], font[role])
        self.assertIn('u"%s"_s' % font['family']['icon'], (CONFIG / 'appearanceconfig.hpp').read_text())

    def test_no_shell_tokens_override(self):
        for path in (ROOT / 'apps').rglob('*'):
            if path.suffix in ('.cpp', '.hpp', '.qml', '.js', '.py', '.md') and path.is_file():
                text = path.read_text(errors='replace')
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertNotIn('shell-tokens.json', text)
                    self.assertNotIn('FontSizeTokens', text)

    def test_shell_loads_the_mono_font(self):
        shell = (ROOT / 'apps/shell/shell.qml').read_text()
        self.assertIn('assets/fonts/CaskaydiaCoveNerdFont-Regular.ttf', shell)


class InstallerTests(unittest.TestCase):
    def test_installer_deploys_tokens(self):
        calls = []

        class Deployment:
            source = ROOT
            conflicts = []

            def deploy(self, source, relative):
                calls.append((Path(source), Path(relative)))

        wayland.deploy_tokens(Deployment())
        self.assertEqual(calls, [(TOKENS, Path('.local/share/wysun/theme/tokens.json'))])
        for step in (wayland.configure, wayland.update_runtime):
            with self.subTest(step=step.__name__):
                self.assertIn('deploy_tokens(d)', inspect.getsource(step))


@unittest.skipUnless(os.environ.get('WYSUN_TEST_RUNTIME'), 'WYSUN_TEST_RUNTIME (runtime built from this tree) not set')
class PluginTests(unittest.TestCase):
    def probe(self, document):
        runtime = Path(os.environ['WYSUN_TEST_RUNTIME'])
        with tempfile.TemporaryDirectory(prefix='wysun-tokens-') as tmp:
            home = Path(tmp)
            env = dict(os.environ, HOME=tmp, QT_QPA_PLATFORM='offscreen',
                       QML_IMPORT_PATH=str(runtime / 'shell/lib/qt6/qml'))
            for key, sub in (('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_STATE_HOME', 'state'),
                             ('XDG_CACHE_HOME', 'cache'), ('XDG_RUNTIME_DIR', 'run')):
                (home / sub).mkdir(mode=0o700)
                env[key] = str(home / sub)
            env['XDG_DATA_DIRS'] = str(home / 'none')
            if document is not None:
                target = home / 'data/wysun/theme/tokens.json'
                target.parent.mkdir(parents=True)
                target.write_text(document if isinstance(document, str) else json.dumps(document))
            qml = next((runtime / 'qt').glob('*/gcc_64/bin/qml'))
            result = subprocess.run([str(qml), str(ROOT / 'tests/shell_tokens_probe.qml')], env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        line = next((l for l in result.stdout.splitlines() if 'TOKENS ' in l), None)
        self.assertIsNotNone(line, result.stdout)
        return json.loads(line.split('TOKENS ', 1)[1]), result.stdout

    def test_plugin_reads_tokens_json(self):
        data = tokens()
        data['rounding']['small'] = 9
        data['spacing']['large'] = 17
        data['anim']['durations']['normal'] = 410
        data['anim']['curves']['standard'] = [0.25, 0, 0, 1, 1, 1]
        values, _ = self.probe(data)
        self.assertEqual(values['roundingSmall'], 9)
        self.assertEqual(values['spacingLarge'], 17)
        self.assertEqual(values['paddingMedium'], data['padding']['medium'])
        self.assertEqual(values['durationNormal'], 410)
        self.assertEqual(values['curveStandard'], [0.25, 0, 0, 1, 1, 1])

    def test_without_tokens_json_the_fallback_applies(self):
        values, output = self.probe(None)
        self.assertEqual(values['roundingSmall'], 8)
        self.assertEqual(values['durationNormal'], 400)
        self.assertIn('tokens.json', output)

    def test_a_value_of_another_type_keeps_its_fallback(self):
        data = tokens()
        data['rounding']['small'] = '9'
        data['rounding']['medium'] = 13
        values, _ = self.probe(data)
        self.assertEqual(values['roundingSmall'], 8)
        self.assertEqual(values['roundingMedium'], 13)

    def test_an_unreadable_file_keeps_every_fallback(self):
        values, output = self.probe('{"rounding": ')
        self.assertEqual(values['roundingSmall'], 8)
        self.assertIn('tokens.json', output)


if __name__ == '__main__':
    unittest.main()
