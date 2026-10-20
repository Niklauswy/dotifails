"""Fixture-only tests for the Wysun desktop providers; no bus or devices."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wysun_desktop_controls", HERE.parent / "services/desktop_controls.py")
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class Fake:
    def __init__(self, available, responses):
        self.available = set(available)
        self.responses = {tuple(k): v for k, v in responses}
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        value = self.responses.get(tuple(argv), "")
        if isinstance(value, Exception):
            raise value
        return value

    def provider(self, **kwargs):
        return desktop.Providers(self, lambda name: name in self.available, environ={}, **kwargs)


def dunst_item(nid, app="Mensajes", summary="Hola", body="<b>Cuerpo</b> &amp; texto", urgency="normal"):
    return {key: {"type": "s", "data": str(value)} for key, value in
            (("id", nid), ("appname", app), ("summary", summary), ("body", body), ("urgency", urgency))}


def history_payload(*items):
    return json.dumps({"type": "aa{sv}", "data": [[dunst_item(*item) for item in items]]})


def session_responses(value="('yes',)"):
    return [(["gdbus", "call", "--system", "--dest", "org.freedesktop.login1",
              "--object-path", "/org/freedesktop/login1", "--method",
              "org.freedesktop.login1.Manager.Can" + name], value) for name in ("Suspend", "Reboot", "PowerOff")]


BLUETOOTH = [(["bluetoothctl", "show"], "Controller 00:11:22:33:44:55\n\tPowered: yes\n"),
             (["bluetoothctl", "devices", "Paired"], "Device AA:BB:CC:DD:EE:FF Auriculares\n")]
NETWORK = [(["nmcli", "-t", "-f", "WIFI", "radio"], "enabled"),
           (["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
            "wlan0:wifi:connected:Casa\\: principal\neth0:ethernet:disconnected:"),
           (["nmcli", "-t", "-f", "UUID,NAME,TYPE", "connection", "show"],
            "12345678-1234-1234-1234-123456789abc:Casa\\: principal:802-11-wireless\n")]


class HistoryTests(unittest.TestCase):
    def test_typed_dunst_values_become_inert_cards(self):
        rows = desktop.history(history_payload((7, "Correo", "<i>Resumen</i>", "<b>Cuerpo</b>"), (8, "Chat", "Hola", "Texto", "critical")))
        self.assertEqual([r["id"] for r in rows], ["7", "8"])
        self.assertEqual(rows[0]["summary"], "Resumen")
        self.assertEqual(rows[0]["body"], "Cuerpo")
        self.assertEqual(rows[1]["urgency"], "critical")
        self.assertEqual(rows[0]["actions"], [], "Dunst keeps ownership of actions")

    def test_invalid_ids_and_shapes_are_dropped(self):
        payload = json.dumps({"data": [[dunst_item("0"), dunst_item("999999999999"), dunst_item("4"), dunst_item("4")]]})
        self.assertEqual([r["id"] for r in desktop.history(payload)], ["4"])
        for bad in ('[]', '{"data": 3}', '{"data": [3]}', 'not json'):
            with self.assertRaises((desktop.Error, ValueError)):
                desktop.history(bad)

    def test_history_is_bounded(self):
        rows = desktop.history(history_payload(*[(n, "App", "Aviso", "Cuerpo") for n in range(1, 130)]))
        self.assertEqual(len(rows), 100)

    def test_html_is_plain_and_nul_removed(self):
        self.assertEqual(desktop.plain("<b>Hola</b>\x00 <script>x</script>"), "Hola x")


class DunstFormatTests(unittest.TestCase):
    def test_real_dunst_uppercases_urgency_and_the_card_gets_it_lowercase(self):
        rows = desktop.history(history_payload((5, "Chat", "Hola", "x", "CRITICAL"), (6, "Chat", "Hola", "x", "LOW")))
        self.assertEqual([r["urgency"] for r in rows], ["critical", "low"])


class LaunchTests(unittest.TestCase):
    """Session actions are started, not awaited: suspend blocks until resume."""

    def provider(self):
        return desktop.Providers(environ={"PATH": "/usr/bin:/bin"}, available=lambda name: True)

    def test_a_long_running_command_is_accepted_after_the_grace_period(self):
        self.assertEqual(self.provider().launch(["sleep", "2"]), "")

    def test_an_immediate_failure_is_reported(self):
        with self.assertRaises(desktop.Error):
            self.provider().launch(["false"])

    def test_a_missing_binary_is_reported(self):
        with self.assertRaises(desktop.Error):
            self.provider().launch(["/nonexistent/wysun-test"])


class ParsingTests(unittest.TestCase):
    def test_nmcli_escaped_colons_and_backslashes(self):
        self.assertEqual(desktop.nmfields(r"wlan0:wifi:connected:Casa\: principal"), ["wlan0", "wifi", "connected", "Casa: principal"])
        self.assertEqual(desktop.nmfields(r"a:b\\c:d"), ["a", "b\\c", "d"])

    def test_percentage_rejects_negative_and_over_100(self):
        for value in ("-1", "101", "x", ""):
            with self.assertRaises(desktop.Error):
                desktop.percent(value)
        self.assertEqual(desktop.percent("0"), 0)
        with self.assertRaises(desktop.Error):
            desktop.percent("4", minimum=5)

    def test_network_uses_terse_parsing_and_keeps_uuids(self):
        provider = Fake(["nmcli"], NETWORK).provider()
        state = provider.network()
        self.assertTrue(state["enabled"])
        self.assertEqual(state["devices"][0]["connection"], "Casa: principal")
        self.assertEqual(state["saved"][0]["uuid"], "12345678-1234-1234-1234-123456789abc")

    def test_bluetooth_only_lists_paired_devices(self):
        state = Fake(["bluetoothctl"], BLUETOOTH).provider().bluetooth()
        self.assertTrue(state["enabled"])
        self.assertEqual(state["devices"], [{"address": "AA:BB:CC:DD:EE:FF", "name": "Auriculares"}],
                         "discovery is never started")

    def test_battery_reads_battery_supplies_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device = root / "hidpp_battery_0"
            device.mkdir()
            (device / "type").write_text("Battery\n")
            (device / "scope").write_text("Device\n")
            (device / "capacity").write_text("40\n")
            battery = root / "BAT0"
            battery.mkdir()
            (battery / "type").write_text("Battery\n")
            (battery / "capacity").write_text("81\n")
            (battery / "status").write_text("Charging\n")
            state = desktop.Providers(available=lambda name: True, environ={}, power_root=root).battery()
            self.assertEqual(state["percent"], 81)
            self.assertEqual(state["status"], "Cargando")


class SnapshotTests(unittest.TestCase):
    def test_missing_provider_is_localised_and_isolated(self):
        with tempfile.TemporaryDirectory() as temporary:
            provider = Fake([], []).provider(power_root=temporary)
            states = provider.snapshot(["network", "bluetooth", "battery"])
            self.assertEqual({key: value["available"] for key, value in states.items()},
                             {"network": False, "bluetooth": False, "battery": False})
            self.assertTrue(all(value["error"] for value in states.values()))

    def test_timeout_becomes_provider_error_without_raising(self):
        provider = Fake(["dunstctl"], [(["dunstctl", "get-pause-level"], desktop.Error("El proveedor no respondió a tiempo"))]).provider()
        state = provider.snapshot(["notifications"])["notifications"]
        self.assertFalse(state["available"])
        self.assertIn("no respondió", state["error"])

    def test_unknown_domain_is_rejected(self):
        with self.assertRaises(desktop.Error):
            Fake([], []).provider().snapshot(["audio"])

    def test_session_permissions_accept_yes_and_challenge_but_not_no(self):
        for value, expected in (("('yes',)", True), ("('challenge',)", True), ("('no',)", False)):
            state = Fake(["gdbus"], session_responses(value)).provider().session()
            self.assertEqual(state["canSuspend"], expected)


class ActionTests(unittest.TestCase):
    def notifications(self, *items):
        return Fake(["dunstctl"], [(["dunstctl", "get-pause-level"], "0"),
                                   (["dunstctl", "history"], history_payload(*items))])

    def test_pause_toggle_and_removal_are_validated_from_fresh_state(self):
        fake = self.notifications((5, "Chat", "Hola", "Texto"))
        provider = fake.provider()
        provider.perform("notifications-pause")
        self.assertIn(["dunstctl", "set-pause-level", "100"], fake.calls)
        provider.perform("notifications-remove", "5")
        self.assertIn(["dunstctl", "history-rm", "5"], fake.calls)

    def test_unknown_or_stale_notification_is_never_removed(self):
        fake = self.notifications((5, "Chat", "Hola", "Texto"))
        provider = fake.provider()
        for value in ("", "6", "5; rm -rf /", "../5"):
            with self.assertRaises(desktop.Error):
                provider.perform("notifications-remove", value)
        self.assertFalse(any(call[:2] == ["dunstctl", "history-rm"] for call in fake.calls))

    def test_clear_requires_history_and_never_removes_popups(self):
        fake = self.notifications((1, "Chat", "Hola", "Texto"))
        fake.provider().perform("notifications-clear")
        self.assertIn(["dunstctl", "history-clear"], fake.calls)
        empty = Fake(["dunstctl"], [(["dunstctl", "get-pause-level"], "0"),
                                    (["dunstctl", "history"], json.dumps({"data": [[]]}))])
        with self.assertRaises(desktop.Error):
            empty.provider().perform("notifications-clear")
        self.assertNotIn(["dunstctl", "close-all"], empty.calls)

    def test_network_and_bluetooth_values_must_exist_in_current_snapshot(self):
        network = Fake(["nmcli"], NETWORK)
        with self.assertRaises(desktop.Error):
            network.provider().perform("network-connect", "not-a-uuid")
        self.assertFalse(any(call[:3] == ["nmcli", "--wait", "2"] for call in network.calls))
        bluetooth = Fake(["bluetoothctl"], BLUETOOTH)
        with self.assertRaises(desktop.Error):
            bluetooth.provider().perform("bluetooth-connect", "00:00:00:00:00:00")
        self.assertFalse(any(call[:2] == ["bluetoothctl", "connect"] for call in bluetooth.calls))

    def test_toggle_commands_are_argv_arrays(self):
        network = Fake(["nmcli"], NETWORK)
        network.provider().perform("network-toggle")
        self.assertIn(["nmcli", "radio", "wifi", "off"], network.calls)
        bluetooth = Fake(["bluetoothctl"], BLUETOOTH)
        bluetooth.provider().perform("bluetooth-toggle")
        self.assertIn(["bluetoothctl", "power", "off"], bluetooth.calls)

    def test_session_lock_and_suspend_use_the_lock_backend(self):
        fake = Fake(["gdbus", "wysun"], session_responses())
        provider = fake.provider()
        provider.perform("session-lock")
        self.assertIn(["wysun", "lock"], fake.calls)
        provider.perform("session-suspend")
        self.assertIn(["wysun", "lock", "--suspend"], fake.calls)

    def test_session_power_actions_respect_permissions(self):
        allowed = Fake(["gdbus", "systemctl"], session_responses())
        allowed.provider().perform("session-poweroff")
        self.assertIn(["systemctl", "poweroff"], allowed.calls)
        denied = Fake(["gdbus", "systemctl"], session_responses("('no',)"))
        with self.assertRaises(desktop.Error):
            denied.provider().perform("session-reboot")
        self.assertFalse(any(call[:1] == ["systemctl"] for call in denied.calls))

    def test_logout_only_dispatches_the_compositor_exit(self):
        fake = Fake(["gdbus", "hyprctl"], session_responses())
        fake.provider().perform("session-logout")
        self.assertIn(["hyprctl", "dispatch", "hl.dsp.exit()"], fake.calls)

    def test_actions_on_unavailable_providers_change_nothing(self):
        for action in ("network-toggle", "bluetooth-toggle", "notifications-pause"):
            fake = Fake([], [])
            with self.assertRaises(desktop.Error):
                fake.provider().perform(action)
            self.assertEqual(fake.calls, [])


class FixtureCliTests(unittest.TestCase):
    def fixture(self, directory, items=((3, "Chat", "Hola", "Texto"),)):
        root = Path(directory)
        (root / "fixture-power/BAT0").mkdir(parents=True)
        (root / "fixture-power/BAT0/type").write_text("Battery\n")
        (root / "fixture-power/BAT0/capacity").write_text("55\n")
        (root / "fixture-power/BAT0/status").write_text("Discharging\n")
        path = root / "fixture.json"
        path.write_text(json.dumps(dict(
            available=["dunstctl", "nmcli", "bluetoothctl", "gdbus", "wysun", "systemctl", "hyprctl"],
            responses=[dict(argv=argv, stdout=stdout) for argv, stdout in
                       [(["dunstctl", "get-pause-level"], "25"),
                        (["dunstctl", "history"], history_payload(*items)),
                        *([(["dunstctl", "history-rm", str(item[0])], "") for item in items]),
                        (["dunstctl", "history-clear"], ""),
                        (["dunstctl", "set-pause-level", "100"], ""),
                        (["dunstctl", "set-pause-level", "0"], ""),
                        *NETWORK, *BLUETOOTH, *session_responses()]])))
        return path

    def run_cli(self, *arguments, home):
        env = {"HOME": str(home), "XDG_CONFIG_HOME": str(Path(home) / "config"),
               "XDG_STATE_HOME": str(Path(home) / "state"), "XDG_CACHE_HOME": str(Path(home) / "cache"),
               "PATH": "/usr/bin:/bin", "LC_ALL": "C"}
        return subprocess.run(["/usr/bin/python3", str(HERE.parent / "services/desktop_controls.py"), *arguments],
                              capture_output=True, text=True, env=env, timeout=20)

    def test_fixture_snapshot_uses_only_declared_responses(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            path = self.fixture(temporary)
            result = self.run_cli("snapshot", "network,bluetooth,battery,notifications", "--fixture", str(path), home=home)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["states"]["battery"]["percent"], 55)
            self.assertEqual(payload["states"]["notifications"]["pauseLevel"], 25)
            self.assertEqual(payload["states"]["notifications"]["items"][0]["summary"], "Hola")
            self.assertEqual(list(home.iterdir()), [], "fixture mode never writes HOME")

    def test_fixture_action_never_touches_the_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            path = self.fixture(temporary)
            result = self.run_cli("action", "notifications-remove", "3", "--fixture", str(path), home=home)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["simulated"])
            self.assertFalse(payload["applied"])

    def test_fixture_rejection_returns_a_safe_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            path = self.fixture(temporary)
            result = self.run_cli("action", "notifications-remove", "99", "--fixture", str(path), home=home)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("99", result.stdout)
            self.assertIn("No se pudo completar", result.stdout)


class OwnershipTests(unittest.TestCase):
    def test_provider_never_starts_a_notification_server_or_toast(self):
        text = (HERE.parent / "services/desktop_controls.py").read_text()
        for forbidden in ("NotificationServer", "notify-send", "dunstify", "shell=True", "os.system("):
            self.assertNotIn(forbidden, text)

    def test_dunst_commands_are_read_only_except_history_and_pause_control(self):
        text = (HERE.parent / "services/desktop_controls.py").read_text()
        verbs = set(re.findall(r'"(dunstctl)",\s*"([a-z-]+)"', text))
        self.assertEqual({verb for tool, verb in verbs if tool == "dunstctl"},
                         {"get-pause-level", "history", "set-pause-level", "history-rm", "history-clear"})

    def test_osd_audio_and_brightness_are_not_duplicated_in_python(self):
        text = (HERE.parent / "services/desktop_controls.py").read_text()
        self.assertNotIn("wpctl", text)
        self.assertNotIn("brightnessctl", text)
        self.assertIn('DOMAINS = ("network", "bluetooth", "battery", "notifications", "session")', text)


if __name__ == "__main__":
    unittest.main()
