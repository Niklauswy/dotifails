"""wysun-lock launcher: Wysun lock by default, swaylock fallback, preview and shader cache.

Everything runs against a fake runtime and fake lockers in a temporary tree: nothing locks.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
LOCK = SOURCE / 'bin/wysun-lock'


def executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


class WysunLockLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wysun-lock-test-')
        self.root = Path(self.temp.name)
        self.shell = self.root / 'shell'
        self.runtime = self.root / 'runtime'
        self.log = self.root / 'calls.log'
        (self.shell / 'wysun').mkdir(parents=True)
        shutil.copy(SOURCE / 'apps/shell/wysun/runtime.sh', self.shell / 'wysun/runtime.sh')
        (self.shell / 'lock.qml').write_text('// lock\n')
        (self.shell / 'lock-preview.qml').write_text('// preview\n')
        shaders = self.shell / 'modules/lockscreen/shaders'
        shaders.mkdir(parents=True)
        (shaders / 'field.frag').write_text('#version 440\n')
        executable(self.runtime / 'qt/6.9.3/gcc_64/bin/qsb',
                   '#!/bin/sh\necho qsb >> "$LOG"\nwhile [ "$1" != -o ]; do shift; done\nprintf qsb > "$2"\n')
        self.bin = self.root / 'bin'
        executable(self.bin / 'swaylock', '#!/bin/sh\necho swaylock >> "$LOG"\n')
        self.quickshell('locks')

    def tearDown(self):
        self.temp.cleanup()

    def quickshell(self, mode):
        body = {
            # Records its entry and the shader directory, then behaves as asked.
            'locks': 'printf locked > "$WYSUN_LOCK_READY"\n',
            'fails': 'exit 3\n',
            'preview': '',
        }[mode]
        executable(self.runtime / 'quickshell/bin/quickshell',
                   '#!/bin/sh\necho "quickshell $2 shaders=$WYSUN_LOCK_SHADERS" >> "$LOG"\n' + body)

    def run_lock(self, *args, config=None):
        env = dict(os.environ, LOG=str(self.log), WYSUN_SHELL_ROOT=str(self.shell), WYSUN_RUNTIME=str(self.runtime),
                   XDG_SESSION_TYPE='wayland', WAYLAND_DISPLAY='wayland-test', XDG_RUNTIME_DIR=str(self.root),
                   XDG_CACHE_HOME=str(self.root / 'cache'), XDG_CONFIG_HOME=str(self.root / 'config'),
                   PATH=str(self.bin) + ':' + os.environ['PATH'], WYSUN_LOCK_WAIT='3')
        env.pop('WYSUN_LOCK_BACKEND', None)
        if config:
            (self.root / 'config/orbit').mkdir(parents=True, exist_ok=True)
            (self.root / 'config/orbit/lock.json').write_text(config)
        return subprocess.run(['sh', str(LOCK), *args], env=env, capture_output=True, text=True, timeout=20)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_the_wysun_lock_is_the_default_and_confirms(self):
        result = self.run_lock()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertTrue(any(call.startswith('quickshell ' + str(self.shell / 'lock.qml')) for call in calls), calls)
        self.assertNotIn('swaylock', calls)
        self.assertEqual(list(self.root.glob('wysun-lock-ready.*')), [])

    def test_shaders_are_compiled_once_into_the_cache(self):
        self.run_lock()
        self.run_lock()
        calls = self.calls()
        self.assertEqual(calls.count('qsb'), 1, calls)
        cached = list((self.root / 'cache/wysun/lock-shaders').glob('*/field.frag.qsb'))
        self.assertEqual(len(cached), 1)
        self.assertIn('shaders=' + str(cached[0].parent), calls[-1])

    def test_failure_before_confirmation_falls_back_to_swaylock(self):
        self.quickshell('fails')
        result = self.run_lock()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls()[-1], 'swaylock')

    def test_missing_runtime_falls_back_to_swaylock(self):
        shutil.rmtree(self.runtime / 'quickshell')
        self.run_lock()
        self.assertEqual(self.calls(), ['swaylock'])

    def test_swaylock_can_still_be_chosen(self):
        self.run_lock(config='{"backend": "swaylock"}')
        self.assertEqual(self.calls(), ['swaylock'])

    def test_preview_never_locks_and_never_uses_swaylock(self):
        self.quickshell('preview')
        result = self.run_lock('--preview')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertTrue(any(call.startswith('quickshell ' + str(self.shell / 'lock-preview.qml')) for call in calls), calls)
        self.assertNotIn('swaylock', calls)
        shutil.rmtree(self.runtime / 'quickshell')
        result = self.run_lock('--preview')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('swaylock', self.calls())

    def test_failed_shader_compilation_keeps_the_lock_and_leaves_no_partial_cache(self):
        executable(self.runtime / 'qt/6.9.3/gcc_64/bin/qsb', '#!/bin/sh\nexit 1\n')
        result = self.run_lock()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('shaders=', self.calls()[-1])
        self.assertTrue(self.calls()[-1].endswith('shaders='))
        self.assertEqual(list((self.root / 'cache/wysun/lock-shaders').glob('*')), [])

    def test_pam_service_delegates_to_the_system_login(self):
        service = (SOURCE / 'apps/shell/assets/pam.d/wysun-lock').read_text()
        rules = [line.split() for line in service.splitlines() if line.strip() and not line.startswith('#')]
        self.assertEqual(rules, [['auth', 'include', '/etc/pam.d/login']])


class LockPaletteTests(unittest.TestCase):
    def test_severance_scheme_is_a_complete_fixed_palette(self):
        import json
        import re
        scheme = json.loads((SOURCE / 'apps/shell/modules/lockscreen/severance-scheme.json').read_text())
        self.assertEqual((scheme['name'], scheme['mode']), ('severance', 'dark'))
        self.assertEqual(set(scheme['colours']), {'surface', 'primary', 'error', 'onSurface', 'onSurfaceVariant', 'success', 'warning', 'info'})
        for value in scheme['colours'].values():
            self.assertRegex(value, r'^[0-9a-f]{6}$')

    def test_founder_film_has_every_frame_it_plays(self):
        import re
        film = (SOURCE / 'apps/shell/modules/lockscreen/FounderFilm.qml').read_text()
        art = SOURCE / 'apps/shell/modules/lockscreen/film'
        for name in re.findall(r'root\.art \+ "([\w-]+\.png)"', film):
            self.assertTrue((art / name).is_file(), name)
        for name, count in re.findall(r'root\.frame\("([\w-]+)", (\d+)', film):
            for index in range(int(count)):
                self.assertTrue((art / f'{name}-{index}.png').is_file(), f'{name}-{index}')
        for index in range(4):
            self.assertTrue((art / f'founder-turn-{index}.png').is_file())



if __name__ == '__main__':
    unittest.main()
