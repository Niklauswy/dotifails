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

    SPEC = json.loads((ROOT / "wysun_theme.json").read_text())

    def selection(self, data, override=None):
        return self.evaluate("selectTheme(%s,%s,%s)" % (json.dumps(self.SPEC), json.dumps(data), json.dumps(override)))

    def test_theme_selection_new_format_and_invalid_variant_fallback(self):
        self.assertEqual(self.selection({"style": "fluent", "variant": "dark"}), {"style": "fluent", "variant": "dark"})
        self.assertEqual(self.selection({"style": "fluent", "variant": "tokyo"}), {"style": "fluent", "variant": "light"})
        self.assertEqual(self.selection({"style": "space-black", "variant": "nope"}), {"style": "space-black", "variant": "space-black"})
        self.assertEqual(self.selection({"style": "space-black", "variant": "tokyo"}), {"style": "space-black", "variant": "tokyo"})

    def test_theme_selection_legacy_aliases_and_overrides(self):
        for legacy, expected in (("Tokyo", ("space-black", "tokyo")), ("azul", ("space-black", "severance")), ("morado", ("space-black", "tokyo")),
                                 ("space-black", ("space-black", "space-black")), ("__proto__", ("space-black", "severance"))):
            self.assertEqual(self.selection({"id": legacy}), {"style": expected[0], "variant": expected[1]}, legacy)
        self.assertEqual(self.selection({}), {"style": "space-black", "variant": "severance"})
        self.assertEqual(self.selection({"style": "space-black", "variant": "tokyo"}, "fluent:dark"), {"style": "fluent", "variant": "dark"})
        self.assertEqual(self.selection({"style": "fluent", "variant": "dark"}, "not-a-theme"), {"style": "fluent", "variant": "dark"})

    def test_resolved_tokens_cover_everything_appearance_reads(self):
        import re
        names = set(re.findall(r'(?:colorOf|numberOf)\("([a-z_]+)"', (ROOT / "Appearance.qml").read_text()))
        self.assertGreater(len(names), 40)
        for style, entry in self.SPEC["styles"].items():
            for variant in entry["variants"]:
                tokens = self.evaluate("resolveTheme(%s,%s,%s)" % (json.dumps(self.SPEC), json.dumps(style), json.dumps(variant)))
                self.assertEqual((tokens["style"], tokens["variant"]), (style, variant))
                self.assertEqual([n for n in sorted(names) if n not in tokens], [], (style, variant))

    def test_token_colours_convert_to_qml_order_and_material_opacity(self):
        self.assertEqual(self.evaluate("[qmlColor('#112233'),qmlColor('#11223344'),qmlColor('red'),qmlColor(undefined)]"),
                         ["#112233", "#44112233", "#00000000", "#00000000"])
        self.assertEqual(self.evaluate("[surfaceOpacity({translucent:true},.7),surfaceOpacity({translucent:false},.7)]"), [.7, 1])

    def test_shell_theme_file_is_the_wysun_copy(self):
        source = ROOT.parents[1] / "apps/wysun/wysun_theme.json"
        self.assertEqual((ROOT / "wysun_theme.json").read_bytes(), source.read_bytes())

    def test_appearance_bounds_match_python_preferences(self):
        self.assertEqual(self.evaluate("[appearance({}), appearance({opacity: 20, reduced_motion: true}), appearance({opacity: '70'})]"),
                         [{"opacity": .8, "reducedMotion": False}, {"opacity": .65, "reducedMotion": True}, {"opacity": .8, "reducedMotion": False}])

    def test_bar_geometry_is_bounded(self):
        self.assertEqual(self.evaluate("barSettings({height:42,offset:9,radius:18}).height"), 42)
        self.assertEqual(self.evaluate("barSettings({height:900,radius:-2}).radius"), 0)
        self.assertEqual(self.evaluate("barSettings({height:900,radius:-2}).offset"), 10)
        self.assertEqual(self.evaluate("barSettings({height:900}).height"), 64)

    def test_bar_custom_colors_and_module_order_survive(self):
        native = {"opacity": 65, "background": "#101118", "foreground": "#EBECF3", "accent": "#B8C8FA",
                  "right": ["notifications", "date", "invalid", "date"], "left": []}
        values = self.evaluate("barSettings(" + json.dumps(native) + ")")
        self.assertEqual(values["background"], "#a6101118")
        self.assertEqual(values["right"], ["notifications", "date"])
        self.assertEqual(values["left"], [])
        self.assertEqual(self.evaluate("barSettings({background:'#000000',opacity:100}).background"), "#ff000000")
        # Without user colours the bar follows the theme.
        unset = self.evaluate("barSettings({})")
        self.assertEqual((unset["background"], unset["foreground"], unset["accent"]), ("", "", ""))

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

    def test_native_bar_values_are_validated(self):
        native = {"height": 48, "radius": 20, "opacity": 80, "background": "#17131f", "foreground": "#e5dcfa", "accent": "#bb9af7", "left": ["title", "orbit"], "right": ["date", "unknown", "date"]}
        values = self.evaluate("barSettings(" + json.dumps(native) + ")")
        self.assertEqual(values["height"], 48)
        self.assertEqual(values["background"], "#cc17131f")
        self.assertEqual(values["left"], ["title", "orbit"])
        self.assertEqual(values["right"], ["date"])
        self.assertEqual(values["center"], ["title"])

    def test_invalid_native_bar_fields_use_safe_defaults(self):
        values = self.evaluate("barSettings({height:'invalid',offset:900,radius:-1,accent:'red',left:[]})")
        self.assertEqual(values["height"], 36)
        self.assertEqual(values["offset"], 60)
        self.assertEqual(values["radius"], 0)
        self.assertEqual(values["accent"], "")  # empty: follow the active theme
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

    def test_workspace_order_is_numeric_and_ten_is_shown_as_zero(self):
        self.assertEqual(self.evaluate("[workspaceLabel({id:10,name:'10'}),workspaceLabel({id:3,name:'3'}),workspaceLabel({id:'web',name:'web'})]"),
                         ["0", "3", "web"])
        self.assertEqual(self.evaluate("sortWorkspaces([{id:10,name:'10'},{id:2,name:'2'},{id:1,name:'1'}]).map(w=>w.id)"),
                         [1, 2, 10])
        self.assertEqual(self.evaluate("sortWorkspaces([{id:'web'},{id:3}]).map(w=>w.id)"), [3, "web"])

    def test_malformed_preferences_are_rejected(self):
        self.assertEqual(self.evaluate("(()=>{try {object('[]');return false;} catch(e){return true;}})()"), True)


if __name__ == "__main__":
    unittest.main()
