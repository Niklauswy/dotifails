"""Exercise the dashboard's JavaScript logic with Node: no compositor, no private data."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "modules/dashboard"


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise QML's JavaScript logic")
class DashboardLogicTests(unittest.TestCase):
    def evaluate(self, expression, setup=""):
        source = (DASHBOARD / "Logic.js").read_text().replace(".pragma library", "", 1)
        result = subprocess.run(["node", "-e", source + "\n" + setup + "\nconsole.log(JSON.stringify(" + expression + "));"],
                                capture_output=True, text=True)
        if result.returncode:
            self.fail(result.stderr[-600:])
        return json.loads(result.stdout)

    def test_missing_samples_are_unavailable_never_zero(self):
        self.assertEqual(self.evaluate("[percentage(null),percentage(undefined),percentage(NaN),percentage(-1),percentage('7')]"),
                         [None] * 5)
        self.assertEqual(self.evaluate("[percentText(null),percentText(0),percentText(41.6),percentText(180)]"),
                         ["No disponible", "0%", "42%", "100%"])
        self.assertEqual(self.evaluate("[arcSweep(null),arcSweep(0),arcSweep(50),arcSweep(100),arcSweep(250)]"), [0, 0, 135, 270, 270])
        self.assertEqual(self.evaluate("[usageLevel(null),usageLevel(10),usageLevel(75),usageLevel(95)]"),
                         ["unknown", "normal", "warning", "critical"])
        self.assertEqual(self.evaluate("[temperatureText(null),temperatureText(61.4)]"), ["Temperatura: no disponible", "61 °C"])

    def test_storage_parser_accepts_wrapped_df_and_rejects_garbage(self):
        wrapped = "Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/mapper/very-long-name\n 100 40 60 40% /"
        self.assertEqual(self.evaluate("storagePercent(%s)" % json.dumps(wrapped)), 40)
        for bad in ("", "x", "Filesystem\n/dev/sda 1 2 3 nope /", None):
            self.assertIsNone(self.evaluate("storagePercent(%s)" % json.dumps(bad)), bad)

    def test_sensor_parser_tolerates_absent_and_hostile_providers(self):
        text = "T coretemp 54000\nT amdgpu 61500\nG 37\nT nvme 99000\nT coretemp 99000"
        self.assertEqual(self.evaluate("parseSensors(%s)" % json.dumps(text)),
                         {"cpuTemperature": 54, "gpuTemperature": 61.5, "gpu": 37})
        empty = {"cpuTemperature": None, "gpuTemperature": None, "gpu": None}
        for hostile in ("", None, "garbage\n\nT\nG", "T coretemp -5\nT coretemp 1e12\nG abc"):
            self.assertEqual(self.evaluate("parseSensors(%s)" % json.dumps(hostile)), empty, hostile)

    def test_player_selection_keeps_manual_choice_then_playing_then_first(self):
        setup = "var a={isPlaying:false},b={isPlaying:true},c={isPlaying:true};"
        self.assertTrue(self.evaluate("activePlayer([a,b,c],a,null)===a", setup))
        self.assertTrue(self.evaluate("activePlayer([a,b,c],null,c)===c", setup))
        self.assertTrue(self.evaluate("activePlayer([a,b,c],null,a)===b", setup))
        self.assertTrue(self.evaluate("activePlayer([a],null,null)===a", setup))
        self.assertIsNone(self.evaluate("activePlayer([],null,null)"))
        self.assertIsNone(self.evaluate("activePlayer(undefined,undefined,undefined)"))

    def test_artwork_is_local_only_and_timestamps_are_safe(self):
        self.assertEqual(self.evaluate("[localArtwork('file:///tmp/a.png'),localArtwork('https://x/y.png'),localArtwork(null)]"),
                         ["file:///tmp/a.png", "", ""])
        self.assertEqual(self.evaluate("[timestamp(75.9),timestamp(-1),timestamp(NaN),timestamp(undefined),timestamp(3600)]"),
                         ["1:15", "—", "—", "—", "60:00"])
        self.assertEqual(self.evaluate("[progressFraction(30,60),progressFraction(90,60),progressFraction(1,0),progressFraction(null,5)]"),
                         [0.5, 1, 0, 0])

    def test_calendar_has_six_monday_first_rows_and_marks_today(self):
        weeks = self.evaluate("monthGrid(2026,9,new Date(2026,9,20))")  # octubre 2026: jueves 1
        self.assertEqual(len(weeks), 6)
        self.assertTrue(all(len(row) == 7 for row in weeks))
        self.assertEqual([c["day"] for c in weeks[0]], [28, 29, 30, 1, 2, 3, 4])
        self.assertEqual([c["inMonth"] for c in weeks[0]], [False, False, False, True, True, True, True])
        marked = [c["day"] for row in weeks for c in row if c["today"]]
        self.assertEqual(marked, [20])
        # A February that starts on Monday still yields six rows.
        feb = self.evaluate("monthGrid(2027,1,null)")
        self.assertEqual((len(feb), feb[0][0]["day"], feb[0][0]["inMonth"]), (6, 1, True))
        self.assertFalse(any(c["today"] for row in feb for c in row))

    def test_month_navigation_wraps_years_and_names_are_spanish(self):
        self.assertEqual(self.evaluate("[shiftMonth(2026,11,1),shiftMonth(2026,0,-1),shiftMonth(2026,5,0)]"),
                         [{"year": 2027, "month": 0}, {"year": 2025, "month": 11}, {"year": 2026, "month": 5}])
        self.assertEqual(self.evaluate("[monthTitle(2026,2),monthTitle(2026,14)]"), ["marzo 2026", "marzo 2026"])
        self.assertEqual(self.evaluate("[dateText(new Date(2026,9,20)),dateText(null),clockText(new Date(2026,0,1,7,5)),clockText(null)]"),
                         ["martes 20 de octubre", "", "07:05", "--:--"])

    def test_desktops_exclude_special_and_other_monitors_and_sort_numerically(self):
        spaces = [
            {"id": 10, "name": "10", "monitor": {"name": "A"}},
            {"id": 2, "name": "2", "monitor": {"name": "A"}},
            {"id": -99, "name": "special:scratch", "monitor": {"name": "A"}},
            {"id": 3, "name": "3", "monitor": {"name": "B"}},
            None,
        ]
        names = self.evaluate("desktops(%s,'A').map(function(w){return w.name})" % json.dumps(spaces))
        self.assertEqual(names, ["2", "10"])
        self.assertEqual(len(self.evaluate("desktops(%s,'')" % json.dumps(spaces))), 3)
        self.assertEqual(self.evaluate("desktops(undefined,'A')"), [])

    def test_windows_of_desktop_handles_missing_workspace_links(self):
        windows = [{"title": "a", "workspace": {"id": 1}}, {"title": "b", "lastIpcObject": {"workspace": {"id": 1}}},
                   {"title": "c", "workspace": {"id": 2}}, {"title": "d"}, None]
        titles = self.evaluate("windowsOfDesktop(%s,{id:1}).map(function(w){return w.title})" % json.dumps(windows))
        self.assertEqual(titles, ["a", "b"])
        self.assertEqual(self.evaluate("windowsOfDesktop(null,{id:1})"), [])
        self.assertEqual(self.evaluate("windowsOfDesktop([],null)"), [])
        self.assertEqual(self.evaluate("[windowTitle({title:'T'}),windowTitle({appId:'x'}),windowTitle(null)]"),
                         ["T", "x", "Ventana sin título"])

    def test_tab_index_is_clamped(self):
        self.assertEqual(self.evaluate("[clampTab(-3,4),clampTab(9,4),clampTab(2.4,4),clampTab('x',4),clampTab(undefined,4)]"), [0, 3, 2, 0, 0])


if __name__ == "__main__":
    unittest.main()
