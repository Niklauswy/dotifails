"""Display arrangement: no overlaps or gaps, reorder, persist and restore."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
import display_layout as layout


def monitor(name, x, y=0, mode='1920x1080', **extra):
    return dict(name=name, enabled=True, primary=False, mode=mode, rate='60.00', rotation='normal', x=x, y=y, scale=1.0) | extra


class LayoutTests(unittest.TestCase):
    def test_dragged_overlap_becomes_edge_to_edge_row_in_centre_order(self):
        # DP-2 dragged over the laptop: it now sits first because its centre is leftmost.
        plan = [monitor('eDP-1', 0), monitor('DP-1', 1920), monitor('DP-2', -700, 40)]
        clean = layout.normalize(plan)
        self.assertEqual(layout.order(clean), ['DP-2', 'eDP-1', 'DP-1'])
        self.assertEqual([(p['name'], p['x'], p['y']) for p in sorted(clean, key=lambda p: p['x'])],
                         [('DP-2', 0, 0), ('eDP-1', 1920, 0), ('DP-1', 3840, 0)])
        self.assertEqual(layout.overlaps(clean), [])

    def test_gaps_are_closed_and_scale_rotation_change_widths(self):
        plan = [monitor('A', 0), monitor('B', 5000, mode='2560x1440', scale=2.0), monitor('C', 9000, rotation='left')]
        clean = {p['name']: p for p in layout.normalize(plan)}
        self.assertEqual((clean['B']['x'], clean['C']['x']), (1920, 1920 + 1280))
        self.assertEqual(layout.logical_size(clean['C']), (1080, 1920))

    def test_move_left_right_swaps_neighbours_and_above_makes_a_row(self):
        plan = layout.normalize([monitor('eDP-1', 0), monitor('DP-1', 1920), monitor('DP-2', 3840)])
        swapped = layout.move(plan, 'DP-2', 'left')
        self.assertEqual(layout.order(swapped), ['eDP-1', 'DP-2', 'DP-1'])
        self.assertEqual(layout.order(layout.move(swapped, 'eDP-1', 'left')), ['eDP-1', 'DP-2', 'DP-1'])
        above = {p['name']: p for p in layout.move(plan, 'eDP-1', 'above')}
        self.assertEqual((above['eDP-1']['x'], above['eDP-1']['y']), (0, 0))
        self.assertEqual((above['DP-1']['y'], above['DP-2']['y']), (1080, 1080))
        self.assertEqual(layout.overlaps(list(above.values())), [])

    def test_disabled_outputs_keep_no_position_and_fragment_disables_them(self):
        plan = layout.normalize([monitor('A', 100), monitor('B', 0, enabled=False)])
        text = layout.monitors_fragment(plan)
        self.assertIn('["output"] = "A"', text)
        self.assertIn('["position"] = "0x0"', text)
        self.assertIn('["disabled"] = true', text)


class RuntimeTests(unittest.TestCase):
    def runner(self, monitors):
        calls = []
        def run(args):
            calls.append(list(args))
            if args[:2] == ['hyprctl', '-j']:
                return json.dumps(monitors if args[2] == 'monitors' else [])
            return 'ok'
        run.calls = calls
        return run

    def hypr(self, name, x):
        return dict(name=name, width=1920, height=1080, scale=1, transform=0, refreshRate=60,
                    availableModes=['1920x1080@60.00Hz'], x=x, y=0, focused=False, disabled=False)

    def test_login_restore_applies_confirmed_profile_and_writes_fragment(self):
        from environment_settings import EnvironmentSettings
        import settings_runtime
        with tempfile.TemporaryDirectory(prefix='wysun-displays-') as folder:
            home = Path(folder)
            live = [self.hypr('eDP-1', 0), self.hypr('DP-1', 1920), self.hypr('DP-2', 3840)]
            run = self.runner(live)
            backend = EnvironmentSettings(home, run)
            profile = [monitor('DP-2', 0), monitor('DP-1', 1920), monitor('eDP-1', 3840)]
            backend.save_section('displays', {'profiles': {'DP-1|DP-2|eDP-1': profile}})
            self.assertTrue(settings_runtime.restore_displays(backend))
            evals = [c for c in run.calls if c[:2] == ['hyprctl', 'eval']]
            self.assertEqual(len(evals), 1)
            self.assertIn('["output"] = "DP-2"', evals[0][2])
            self.assertIn('["position"] = "0x0"', evals[0][2])
            fragment = (home / '.config/orbit/hypr-monitors.lua').read_text()
            self.assertEqual(fragment, layout.monitors_fragment(layout.normalize(profile)))

    def test_without_profile_nothing_changes(self):
        from environment_settings import EnvironmentSettings
        import settings_runtime
        with tempfile.TemporaryDirectory(prefix='wysun-displays-') as folder:
            run = self.runner([self.hypr('eDP-1', 0)])
            self.assertFalse(settings_runtime.restore_displays(EnvironmentSettings(Path(folder), run)))
            self.assertFalse(any(c[:2] == ['hyprctl', 'eval'] for c in run.calls))
            self.assertFalse((Path(folder) / '.config/orbit/hypr-monitors.lua').exists())

    def test_trial_normalizes_saves_profile_fragment_and_refreshes(self):
        from unittest.mock import patch
        import environment_settings as env
        with tempfile.TemporaryDirectory(prefix='wysun-displays-') as folder:
            home = Path(folder)
            run = self.runner([self.hypr('eDP-1', 0), self.hypr('DP-1', 1920)])
            backend = env.EnvironmentSettings(home, run)
            draft = [monitor('eDP-1', 900, 300), monitor('DP-1', 0)]  # overlapping drag
            with patch.object(env.subprocess, 'Popen'), patch.object(env, 'after_display_change') as refresh:
                trial = env.DisplayTrial(backend, draft)
                trial.accept()
            refresh.assert_called_once_with(backend)
            saved = backend.section('displays')['profiles']['DP-1|eDP-1']
            self.assertEqual({p['name']: p['x'] for p in saved}, {'DP-1': 0, 'eDP-1': 1920})
            self.assertEqual((home / '.config/orbit/hypr-monitors.lua').read_text(), layout.monitors_fragment(saved))

    def test_hyprland_config_loads_fragment_after_local_preferences(self):
        text = (Path(__file__).resolve().parents[2] / 'config/.config/wysun/hyprland.lua').read_text()
        self.assertLess(text.index('dofile(localPath)'), text.index('dofile(monitorsPath)'))


if __name__ == '__main__':
    unittest.main()
