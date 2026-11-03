"""The shell modules added for Wysun Processes resolve every type they use: a private quickshell (offscreen, temporary
HOME, no compositor) compiles a probe that instantiates them, so a missing import never reaches the live shell."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / 'apps/shell'
MODULES = ('windowtools', 'anr', 'forcequit')
PROBE = '''import QtQuick
import Quickshell
{imports}

ShellRoot {{
{items}
    Timer {{ interval: 1500; running: true; onTriggered: {{ console.log("PROBE_DONE"); Qt.quit(); }} }}
}}
'''


class ShellModuleLoadTests(unittest.TestCase):
    def probe(self, modules, imports, items):
        runtime = Path.home() / '.local/share/wysun/runtime'
        binary = runtime / 'quickshell/bin/quickshell'
        if not binary.exists():
            self.skipTest('shell runtime not built')
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            shell = home / 'shell'
            shell.mkdir()
            for sub in ('utils', 'components', 'services', 'assets', 'wysun', 'extras'):
                if (SHELL / sub).exists():
                    (shell / sub).symlink_to(SHELL / sub)
            if modules == 'all':
                (shell / 'modules').symlink_to(SHELL / 'modules')
            else:
                (shell / 'modules').mkdir()
                for module in modules:
                    (shell / 'modules' / module).symlink_to(SHELL / 'modules' / module)
            (shell / 'shell.qml').write_text(PROBE.format(imports='\n'.join(imports), items='\n'.join(items)))
            env = dict(os.environ, HOME=tmp, QT_QPA_PLATFORM='offscreen', WAYLAND_DISPLAY='',
                       HYPRLAND_INSTANCE_SIGNATURE='', WYSUN_LIB_DIR=str(runtime / 'shell/lib/wysun'),
                       QML_IMPORT_PATH=os.pathsep.join([str(runtime / 'shell/lib/qt6/qml'),
                                                        str(runtime / 'deps/lib/qt6/qml')]))
            for key, sub in (('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_STATE_HOME', 'state'),
                             ('XDG_CACHE_HOME', 'cache'), ('XDG_RUNTIME_DIR', 'run')):
                (home / sub).mkdir(mode=0o700)
                env[key] = str(home / sub)
            (home / 'data/wysun/theme').mkdir(parents=True)
            (home / 'data/wysun/theme/tokens.json').write_text((ROOT / 'apps/python/wysun_core/tokens.json').read_text())
            (home / 'config/wysun').mkdir(parents=True)
            (home / 'config/wysun/theme.json').write_text(json.dumps({'mode': 'dark'}))
            result = subprocess.run([str(binary), '-p', str(shell)], env=env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=60, cwd=tmp)
        out = result.stdout
        # Without a compositor quickshell has no layer-shell backend: windows cannot be created, but every file was
        # compiled first, so unresolved types and imports still show up as "is not a type".
        no_backend = 'No PanelWindow backend loaded' in out
        hard = ('is not a type', 'is not installed', 'ReferenceError', 'Cannot assign', 'Syntax error', 'Expected token')
        soft = () if no_backend else ('unavailable', 'Failed to load')
        bad = [line for line in out.splitlines() if any(m in line for m in hard + soft)]
        self.assertEqual(bad, [], out[-3000:])
        if not no_backend:
            self.assertIn('PROBE_DONE', out, out[-3000:])

    def test_modules_load_in_a_private_quickshell(self):
        names = {'windowtools': 'WindowTools', 'anr': 'Anr', 'forcequit': 'ForceQuit'}
        present = [m for m in MODULES if (SHELL / 'modules' / m).is_dir()]
        self.probe(present, [f'import qs.modules.{m}' for m in present], [f'    {names[m]} {{}}' for m in present])

    def test_launcher_process_pane_loads(self):
        self.probe('all', ['import qs.modules.launcher'], ['    property Item processPane: ProcessPane {}'])

    def test_alert_settings_page_loads(self):
        # The section of Settings > Notifications that writes ~/.config/wysun/processes.json.
        self.probe('all', ['import qs.modules.nexus.pages.services'],
                   ['    property Item notificationsPage: NotificationsPage {}'])


if __name__ == '__main__':
    unittest.main()
