"""Synthetic control plans/OSD only: no bus, devices, media or host commands."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("wysun_controls", Path(__file__).parents[1] / "controls.py")
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


class Fake:
    def __init__(self, available, responses):
        self.available = set(available)
        self.responses = {tuple(k): v for k, v in responses}
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        value = self.responses.get(tuple(argv), "")
        if isinstance(value, Exception):
            raise value
        return value

    def controller(self):
        return controls.Controller(self, lambda name: name in self.available, environ={})


class ControlsTests(unittest.TestCase):
    def volume(self, text="Volume: 0.45", available=("wpctl", "dunstify")):
        return Fake(available, [(["wpctl", "get-volume", controls.SINK], text)])

    def brightness(self, current=50, maximum=100, name="intel_backlight"):
        text = f"{name},backlight,{current},50%,{maximum}"
        return Fake(("brightnessctl", "notify-send"), [(["brightnessctl", "-m", "-c", "backlight", "info"], text),
            (["brightnessctl", "-m", "-c", "backlight", "-d", name, "info"], text)])

    def test_volume_steps_and_unmute_preserve_previous_keys(self):
        for action, target in (("volume-up", "0.50"), ("volume-down", "0.40")):
            plan = self.volume().controller().plan(action)
            self.assertEqual(plan["commands"], [["wpctl", "set-volume", "-l", "1", controls.SINK, target],
                                                 ["wpctl", "set-mute", controls.SINK, "0"]])

    def test_volume_is_clamped_at_both_limits(self):
        self.assertEqual(self.volume("Volume: 1.00").controller().plan("volume-up")["commands"][0][-1], "1.00")
        self.assertEqual(self.volume("Volume: 0.01").controller().plan("volume-down")["commands"][0][-1], "0.00")

    def test_invalid_volume_never_mutates(self):
        fake = self.volume("not a volume")
        with self.assertRaises(controls.ControlError):
            fake.controller().perform("volume-up")
        self.assertEqual(len(fake.calls), 1)

    def test_pactl_backend_is_selected_before_mutation(self):
        fake = Fake(("pactl",), [(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], "front-left: 29491 / 45% / -20 dB"),
                                (["pactl", "get-sink-mute", "@DEFAULT_SINK@"], "Mute: no")])
        plan = fake.controller().plan("volume-up")
        self.assertEqual(plan["commands"][0], ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "50%"])

    def test_volume_feedback_is_actual_state_and_has_replacement_tag(self):
        fake = self.volume("Volume: 0.45 [MUTED]")
        result = fake.controller().perform("volume-mute")
        self.assertTrue(result["notification_sent"])
        notice = fake.calls[-1]
        self.assertIn("int:value:0", notice)
        self.assertIn("string:x-dunst-stack-tag:wysun-volume", notice)
        self.assertIn("audio-volume-muted-symbolic", notice)
        self.assertEqual(notice[-1], "Silenciado")
        self.assertFalse(any("set-paused" in call or "reload" in call for call in fake.calls))

    def test_brightness_floor_ceiling_and_tiny_device(self):
        for current, maximum, action, target in ((1, 100, "brightness-down", "5"), (100, 100, "brightness-up", "100"),
                                                (1, 4, "brightness-down", "1"), (50, 100, "brightness-up", "55")):
            self.assertEqual(self.brightness(current, maximum).controller().plan(action)["commands"][0][-1], target)

    def test_brightness_only_explicit_backlight_not_leds_or_globs(self):
        for name in ("kbd*", "../intel", "-device"):
            fake = self.brightness(name=name)
            with self.assertRaises(controls.ControlError):
                fake.controller().perform("brightness-down")
            self.assertEqual(len(fake.calls), 1)

    def test_brightness_osd_uses_its_own_progress_tag(self):
        fake = self.brightness()
        result = fake.controller().perform("brightness-up")
        self.assertTrue(result["notification_sent"])
        self.assertIn("string:x-dunst-stack-tag:wysun-brightness", fake.calls[-1])
        self.assertIn("int:value:50", fake.calls[-1])  # Readback, not predicted55.

    def test_media_mpd_precedence_including_stop_and_toggle(self):
        for action, verb in (("media-stop", "stop"), ("media-next", "next"), ("media-previous", "prev"), ("media-play-pause", "toggle")):
            fake = Fake(("mpc", "playerctl"), [(["mpc", "--format", "", "status"], "[playing] #1/2")])
            result = fake.controller().perform(action)
            self.assertEqual(result["backend"], "mpc")
            self.assertEqual(fake.calls[-1], ["mpc", verb])
            self.assertFalse(any(call[0] == "playerctl" for call in fake.calls))

    def test_mpd_failure_before_selection_falls_back_to_one_player(self):
        fake = Fake(("mpc", "playerctl"), [(["mpc", "--format", "", "status"], controls.ControlError("MPD absent")),
            (["playerctl", "--list-all"], "browser.instance1\nwysun.instance2"),
            (["playerctl", "--player", "browser.instance1", "status"], "Paused"),
            (["playerctl", "--player", "wysun.instance2", "status"], "Playing")])
        result = fake.controller().perform("media-stop")
        self.assertEqual(result["player"], "wysun.instance2")
        self.assertEqual(fake.calls[-1], ["playerctl", "--player", "wysun.instance2", "stop"])

    def test_failed_media_stop_never_targets_another_player(self):
        fake = Fake(("mpc", "playerctl"), [(["mpc", "--format", "", "status"], "[paused] #1/2"),
                                          (["mpc", "stop"], controls.ControlError("failed"))])
        with self.assertRaises(controls.ControlError):
            fake.controller().perform("media-stop")
        self.assertEqual(fake.calls, [["mpc", "--format", "", "status"], ["mpc", "stop"]])

    def test_failed_volume_never_retries_other_backend_or_notifies(self):
        fake = self.volume(available=("wpctl", "pactl", "dunstify"))
        fake.responses[("wpctl", "set-volume", "-l", "1", controls.SINK, "0.50")] = controls.ControlError("failed")
        with self.assertRaises(controls.ControlError):
            fake.controller().perform("volume-up")
        self.assertEqual(len(fake.calls), 2)

    def test_missing_osd_is_reported_separately_from_applied_action(self):
        fake = self.volume(available=("wpctl",))
        result = fake.controller().perform("volume-up")
        self.assertEqual(result["result"], "APPLIED_OSD_FAILED")
        self.assertTrue(result["applied"])
        self.assertFalse(result["notification_sent"])

    def test_dry_run_never_executes_action_or_notification(self):
        for action in ("volume-up", "volume-down", "volume-mute"):
            fake = self.volume()
            self.assertFalse(fake.controller().perform(action, dry_run=True)["applied"])
            self.assertEqual(fake.calls, [["wpctl", "get-volume", controls.SINK]])
        fake = self.brightness()
        fake.controller().perform("brightness-down", dry_run=True)
        self.assertEqual(len(fake.calls), 1)

    def test_appimage_loader_is_removed_without_changing_session_bus(self):
        env = controls.host_environment(dict(APPDIR="/tmp/.mount_test", APPIMAGE="fixture", LD_LIBRARY_PATH="bad",
            LD_PRELOAD="bad", PATH="/tmp/.mount_test/usr/bin:/usr/bin", DBUS_SESSION_BUS_ADDRESS="unix:path=/fixture/bus"))
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertNotIn("LD_LIBRARY_PATH", env)
        self.assertNotIn("LD_PRELOAD", env)
        self.assertEqual(env["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/fixture/bus")

    def test_cli_fixture_only_works_in_dry_run(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "responses.json"
            path.write_text(json.dumps(dict(available=["wpctl"], responses=[dict(argv=["wpctl", "get-volume", controls.SINK], stdout="Volume: 0.45")])))
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(controls.main(["volume-up", "--dry-run", "--fixture", str(path)]), 0)
            result = json.loads(output.getvalue())
            self.assertTrue(result["fixture"])
            self.assertFalse(result["applied"])
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                controls.main(["volume-up", "--fixture", str(path)])


if __name__ == "__main__":
    unittest.main()
