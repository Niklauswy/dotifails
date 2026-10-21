"""Fixed per-output workspace layout: defaults, validation and live apply."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
import workspace_layout as layouts


def outputs(*rows):
    return [dict(name=name, enabled=True, x=x, y=0) for name, x in rows]


class LayoutTests(unittest.TestCase):
    def test_defaults_three_outputs_keep_internal_for_last_number(self):
        layout = layouts.default_layout(outputs(('DP-2', 1920), ('DP-1', 0), ('eDP-1', 3840)))
        self.assertEqual(layout, {'DP-1': [1, 2, 3, 4, 5], 'DP-2': [6, 7, 8, 9], 'eDP-1': [10]})

    def test_defaults_two_outputs_split_five_and_five(self):
        self.assertEqual(layouts.default_layout(outputs(('DP-1', 0), ('eDP-1', 1920))),
                         {'DP-1': [1, 2, 3, 4, 5], 'eDP-1': [6, 7, 8, 9, 10]})
        self.assertEqual(layouts.default_layout(outputs(('DP-2', 1920), ('DP-1', 0))),
                         {'DP-1': [1, 2, 3, 4, 5], 'DP-2': [6, 7, 8, 9, 10]})

    def test_defaults_single_output_keeps_every_number(self):
        self.assertEqual(layouts.default_layout(outputs(('HDMI-A-1', 0))), {'HDMI-A-1': list(range(1, 11))})

    def test_normalize_ignores_legacy_or_invalid_values(self):
        stored = {'names': ['keep'], 'DP-1': ['3', 'x', 3, 11, '7'], 'DP-2': ['7'], 'GHOST': ['1']}
        self.assertEqual(layouts.normalize_layout(stored, outputs(('DP-1', 0), ('DP-2', 1920))),
                         {'DP-1': [3, 7]})

    def test_validate_rejects_duplicates_unknown_outputs_and_wrong_numbers(self):
        rows = outputs(('DP-1', 0), ('DP-2', 1920))
        with self.assertRaisesRegex(ValueError, 'ya está en otra pantalla'):
            layouts.validate_layout({'DP-1': [1, 2], 'DP-2': [2, 3]}, rows)
        with self.assertRaisesRegex(ValueError, 'Pantalla desconocida'):
            layouts.validate_layout({'DP-9': [1]}, rows)
        with self.assertRaisesRegex(ValueError, '1 al 10'):
            layouts.validate_layout({'DP-1': [0]}, rows)
        self.assertEqual(layouts.validate_layout({'DP-2': [10, 6]}, rows), {'DP-2': [6, 10]})

    def test_labels_show_ten_as_zero(self):
        self.assertEqual(layouts.workspace_label(10), '0')
        self.assertEqual(layouts.workspace_label('3'), '3')
        self.assertEqual(layouts.workspace_label('web'), 'web')
        self.assertEqual(layouts.workspace_number('10'), 10)

    def test_lua_fragment_pins_and_live_script_releases_removed_pairs(self):
        fragment = layouts.lua_fragment({'DP-1': [1], 'eDP-1': [10]})
        self.assertIn('["persistent"] = true', fragment)
        self.assertIn('hl.workspace_rule', fragment)
        script = layouts.live_script({'DP-2': [1]}, {'DP-1': [1], 'DP-2': [2]})
        self.assertIn('["workspace"] = "1", ["monitor"] = "DP-2", ["persistent"] = true', script)
        self.assertIn('["workspace"] = "1", ["monitor"] = "DP-1", ["persistent"] = false', script)
        self.assertIn('["workspace"] = "2", ["monitor"] = "DP-2", ["persistent"] = false', script)


class SettingsIntegrationTests(unittest.TestCase):
    def runner(self):
        monitors = [
            dict(name='DP-1', width=1920, height=1080, scale=1, transform=0, refreshRate=60,
                 availableModes=['1920x1080@60Hz'], x=0, y=0, focused=True, disabled=False),
            dict(name='eDP-1', width=1920, height=1080, scale=1, transform=0, refreshRate=60,
                 availableModes=['1920x1080@60Hz'], x=1920, y=0, focused=False, disabled=False),
        ]
        workspaces = [dict(id=1, name='1', monitor='DP-1', windows=0),
                      dict(id=10, name='10', monitor='eDP-1', windows=0)]
        calls = []

        def run(args):
            calls.append(list(args))
            if args[:2] == ['hyprctl', '-j']:
                return json.dumps(monitors if args[2] == 'monitors' else workspaces)
            if args[:2] == ['hyprctl', 'eval']:
                return 'ok'
            raise AssertionError('Synthetic runner received '+str(args))
        run.calls = calls
        return run

    def test_apply_persists_environment_and_generated_fragment(self):
        from environment_settings import EnvironmentSettings
        with tempfile.TemporaryDirectory(prefix='wysun-workspace-layout-') as folder:
            home = Path(folder)
            backend = EnvironmentSettings(home, self.runner())
            backend.apply_workspace_layout({'DP-1': [1, 2], 'eDP-1': [10]})
            stored = json.loads((home/'.config/orbit/environment.json').read_text())
            self.assertEqual(stored['workspaces'], {'DP-1': [1, 2], 'eDP-1': [10]})
            fragment = (home/'.config/orbit/hypr-workspaces.lua').read_text()
            self.assertIn('["workspace"] = "10", ["monitor"] = "eDP-1", ["persistent"] = true', fragment)

    def test_assign_moves_number_to_the_chosen_output(self):
        from environment_settings import EnvironmentSettings
        with tempfile.TemporaryDirectory(prefix='wysun-workspace-layout-') as folder:
            home = Path(folder)
            backend = EnvironmentSettings(home, self.runner())
            backend.apply_workspace_layout({'DP-1': list(range(1, 11))})
            backend.assign_workspace(10, 'eDP-1')
            stored = json.loads((home/'.config/orbit/environment.json').read_text())
            self.assertEqual(stored['workspaces'], {'DP-1': list(range(1, 10)), 'eDP-1': [10]})
            scripts = [call for call in backend.runner.calls if call[:2] == ['hyprctl', 'eval']]
            self.assertIn('["workspace"] = "10", ["monitor"] = "eDP-1", ["persistent"] = true', scripts[-1][2])

    def test_workspaces_merges_assigned_empty_slots_with_live_rows(self):
        from environment_settings import EnvironmentSettings
        with tempfile.TemporaryDirectory(prefix='wysun-workspace-layout-') as folder:
            home = Path(folder)
            backend = EnvironmentSettings(home, self.runner())
            backend.apply_workspace_layout({'DP-1': [1], 'eDP-1': [10]})
            rows = backend.workspaces()
            self.assertEqual([row['id'] for row in rows], ['1', '10'])
            self.assertTrue(all(row['fixed'] for row in rows))
            self.assertEqual([row['label'] for row in rows], ['1', '0'])

    def test_workspaces_lists_automatic_layout_without_saved_one(self):
        from environment_settings import EnvironmentSettings
        with tempfile.TemporaryDirectory(prefix='wysun-workspace-layout-') as folder:
            rows = EnvironmentSettings(Path(folder), self.runner()).workspaces()
            self.assertEqual([row['id'] for row in rows], [str(n) for n in range(1, 11)])
            self.assertEqual({row['assigned'] for row in rows if row['number'] <= 5}, {'DP-1'})
            self.assertEqual({row['assigned'] for row in rows if row['number'] > 5}, {'eDP-1'})


class LoginRestoreTests(unittest.TestCase):
    runner = SettingsIntegrationTests.runner

    def restore(self, home, runner):
        import settings_runtime
        from environment_settings import EnvironmentSettings
        settings_runtime.restore_workspaces(EnvironmentSettings(home, runner))
        return [call for call in runner.calls if call[:2] == ['hyprctl', 'eval']]

    def test_defaults_generate_fragment_and_pin_live_without_saving_layout(self):
        with tempfile.TemporaryDirectory(prefix='wysun-workspace-restore-') as folder:
            home = Path(folder)
            runner = self.runner()
            scripts = self.restore(home, runner)
            fragment = (home/'.config/orbit/hypr-workspaces.lua').read_text()
            self.assertEqual(fragment, layouts.lua_fragment({'DP-1': [1, 2, 3, 4, 5], 'eDP-1': [6, 7, 8, 9, 10]}))
            self.assertEqual(len(scripts), 1)
            self.assertIn('["workspace"] = "5", ["monitor"] = "DP-1", ["persistent"] = true', scripts[0][2])
            self.assertNotIn('persistent"] = false', scripts[0][2])
            self.assertFalse((home/'.config/orbit/environment.json').exists())
            # Hotplug events repeat the restore; the fragment stays identical.
            self.restore(home, runner)
            self.assertEqual((home/'.config/orbit/hypr-workspaces.lua').read_text(), fragment)

    def test_saved_layout_wins_over_automatic_one(self):
        from environment_settings import EnvironmentSettings
        with tempfile.TemporaryDirectory(prefix='wysun-workspace-restore-') as folder:
            home = Path(folder)
            EnvironmentSettings(home, self.runner()).apply_workspace_layout({'eDP-1': [1], 'DP-1': [2]})
            (home/'.config/orbit/hypr-workspaces.lua').unlink()
            scripts = self.restore(home, self.runner())
            self.assertIn('["workspace"] = "1", ["monitor"] = "eDP-1", ["persistent"] = true', scripts[0][2])
            self.assertEqual((home/'.config/orbit/hypr-workspaces.lua').read_text(),
                             layouts.lua_fragment({'DP-1': [2], 'eDP-1': [1]}))

    def test_failure_is_reported_without_raising(self):
        def broken(args):
            raise RuntimeError('compositor unavailable')
        broken.calls = []
        with tempfile.TemporaryDirectory(prefix='wysun-workspace-restore-') as folder:
            self.restore(Path(folder), broken)
            self.assertFalse((Path(folder)/'.config/orbit/hypr-workspaces.lua').exists())

    def test_wrapper_runs_installed_runtime(self):
        root = Path(__file__).resolve().parents[2]
        text = (root/'bin/wysun-workspaces').read_text()
        self.assertIn("share/orbit/app/settings_runtime.py", text)
        self.assertIn("'workspaces'", text)
        config = (root/'config/.config/wysun/hyprland.lua').read_text()
        self.assertIn('hl.on("monitor.added", function () hl.exec_cmd("wysun-workspaces") end)', config)
        self.assertIn('"hypr-workspaces.lua"', config)


if __name__ == '__main__':
    unittest.main()
