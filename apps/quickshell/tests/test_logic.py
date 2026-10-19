"""Exercise the actual QML JavaScript data logic, without a compositor or private data."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise QML's JavaScript logic")
class LogicTests(unittest.TestCase):
    def evaluate(self, expression):
        source = (ROOT / "Logic.js").read_text().replace(".pragma library", "", 1)
        result = subprocess.run(
            ["node", "-e", source + "\nconsole.log(JSON.stringify(" + expression + "));"],
            check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)

    def test_theme_identity_and_legacy_aliases(self):
        self.assertEqual(self.evaluate("[themeKey('Tokyo'), themeKey('azul'), themeKey('space-black'), themeKey('__proto__')]"),
                         ["tokyo", "severance", "space-black", "severance"])
        self.assertEqual(self.evaluate("themes['space-black'].accent"), "#ceced4")

    def test_appearance_bounds_match_python_preferences(self):
        self.assertEqual(self.evaluate("[appearance({}), appearance({opacity: 20, reduced_motion: true}), appearance({opacity: '70'})]"),
                         [{"opacity": .8, "reducedMotion": False}, {"opacity": .65, "reducedMotion": True}, {"opacity": .8, "reducedMotion": False}])

    def test_bar_geometry_imported_and_bounded(self):
        text = "[bar/base]\nheight = 42\noffset-y = 9\nradius = 18\n"
        self.assertEqual(self.evaluate("barSettings(" + json.dumps(text) + ").height"), 42)
        self.assertEqual(self.evaluate("barSettings('[bar/base]\\nheight=900\\nradius=-2').radius"), 0)
        self.assertEqual(self.evaluate("barSettings('[bar/base]\\nheight=900\\nradius=-2').offset"), 10)

    def test_bar_custom_colors_and_module_order_survive(self):
        text = "[colors]\nbg=#A6101118\nfg=#EBECF3\naccent=#B8C8FA\n[bar/right]\nmodules-right=notifications date invalid date\n[bar/left]\nmodules-left=\n"
        values = self.evaluate("barSettings(" + json.dumps(text) + ")")
        self.assertEqual(values["background"], "#A6101118")
        self.assertEqual(values["right"], ["notifications", "date"])
        self.assertEqual(values["left"], [])
        self.assertEqual(self.evaluate("barSettings('[colors]\\nbg=#112233',{background:'#000000'}).background"), "#ff000000")

    def test_cpu_and_memory_metrics_handle_first_sample_and_counter_reset(self):
        self.assertIsNone(self.evaluate("cpuSample('cpu 10 0 10 80 0 0 0 0',null).percent"))
        self.assertEqual(self.evaluate("cpuSample('cpu 15 0 15 90 0 0 0 0',cpuSample('cpu 10 0 10 80 0 0 0 0',null)).percent"), 50)
        self.assertIsNone(self.evaluate("cpuSample('cpu 1 0 0 0 0 0 0 0',{total:100,idle:80}).percent"))
        self.assertEqual(self.evaluate("memoryPercent('MemTotal: 1000 kB\\nMemAvailable: 250 kB')"), 75)

    def test_bar_presentation_yields_secondary_info_before_icon_controls(self):
        self.assertEqual(self.evaluate("barPresentation(1256)"),
                         {"showTitle": True, "showResources": True, "iconControls": False, "dateFormat": "d MMM · hh:mm"})
        self.assertEqual(self.evaluate("barPresentation(1000)"),
                         {"showTitle": False, "showResources": False, "iconControls": False, "dateFormat": "hh:mm"})
        self.assertEqual(self.evaluate("barPresentation(640)"),
                         {"showTitle": False, "showResources": False, "iconControls": True, "dateFormat": "hh:mm"})
        self.assertEqual(self.evaluate("[barPresentation(1099).showTitle,barPresentation(1100).showTitle,barPresentation(1199).showResources,barPresentation(1200).showResources]"),
                         [False, True, False, True])

    def test_unavailable_metrics_do_not_display_a_percentage(self):
        self.assertEqual(self.evaluate("[resourceLabel(null,undefined),resourceLabel(0,75)]"),
                         ["CPU — · RAM —", "CPU 0% · RAM 75%"])

    def test_native_bar_overrides_legacy_without_mutating_it(self):
        text = "[colors]\nbg=#A6101118\nfg=#EBECF3\n[bar/base]\nheight=40\n[bar/left]\nmodules-left=orbit title\n"
        native = {"height": 48, "radius": 20, "opacity": 80, "background": "#17131f", "foreground": "#e5dcfa", "accent": "#bb9af7", "left": ["title", "orbit"], "right": ["date", "unknown", "date"]}
        values = self.evaluate("barSettings(" + json.dumps(text) + "," + json.dumps(native) + ")")
        self.assertEqual(values["height"], 48)
        self.assertEqual(values["background"], "#cc17131f")
        self.assertEqual(values["left"], ["title", "orbit"])
        self.assertEqual(values["right"], ["date"])
        self.assertEqual(self.evaluate("barSettings(" + json.dumps(text) + ").height"), 40)

    def test_partial_native_bar_retains_legacy_and_validates_fields(self):
        values = self.evaluate("barSettings('[bar/base]\\nheight=42\\n[colors]\\naccent=#aabbcc',{height:'invalid',offset:900,radius:-1,accent:'red',left:[]})")
        self.assertEqual(values["height"], 42)
        self.assertEqual(values["offset"], 60)
        self.assertEqual(values["radius"], 0)
        self.assertEqual(values["accent"], "#aabbcc")
        self.assertEqual(values["left"], [])

    def test_native_monitor_preferences_win_and_fall_back_on_hotplug(self):
        self.assertEqual(self.evaluate("trayMonitor({bar:{tray_monitor:'A'}},[{name:'A'},{name:'B'}],{monitors:{A:false},tray_monitor:'missing'})"), "B")
        self.assertFalse(self.evaluate("monitorEnabled({bar:{monitors:{A:true}}},'A',{monitors:{A:false}})"))

    def test_hotplug_tray_falls_back_to_first_enabled_monitor(self):
        self.assertEqual(self.evaluate("trayMonitor({bar:{tray_monitor:'HDMI-A-1',monitors:{'eDP-1':false}}},[{name:'eDP-1'},{name:'DP-2'}])"), "DP-2")
        self.assertEqual(self.evaluate("trayMonitor({bar:{monitors:{A:false}}},[{name:'A'}])"), "")
        self.assertEqual(self.evaluate("popupScreen([], 'missing')"), None)

    def test_wallpaper_retains_per_output_mode_and_is_local(self):
        self.assertEqual(self.evaluate("wallpaper({wallpaper:{default:'/backgrounds/shared.png',monitors:{DP:{path:'~/My photos/a #1.png',mode:'fit'}}}},'DP','/home/test','azul.jpg')"),
                         {"path": "/home/test/My photos/a #1.png", "mode": "fit"})
        self.assertEqual(self.evaluate("wallpaper({wallpaper:{default:'https://example.test/private'}},'DP','/home/test','azul.jpg').path"), "")

    def test_only_public_application_commands_are_dispatched(self):
        self.assertEqual(self.evaluate("[allowedCommand('notes'),allowedCommand('lock'),allowedCommand('sh'),allowedCommand('notes; touch /tmp/no'),allowedCommand('__proto__')]"),
                         [True, True, False, False, False])
        self.assertEqual(self.evaluate("filteredApplications('portapapeles').map(x=>x.command)"), ["clipboard"])
        expected = {"launcher", "clipboard", "music", "files", "notes", "colors", "screenshot", "recorder", "processes", "tools", "connections", "notifications", "settings", "power"}
        self.assertEqual(set(self.evaluate("applications.map(x=>x.command)")), expected)
        self.assertEqual(self.evaluate("[allowedCommand('screenshot'),allowedCommand('recorder')]"), [True, True])

    def test_malformed_preferences_are_rejected(self):
        self.assertEqual(self.evaluate("(()=>{try {object('[]');return false;} catch(e){return true;}})()"), True)


if __name__ == "__main__":
    unittest.main()
