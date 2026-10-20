"""Launcher logic, bounded arithmetic, allowlist and wallpaper adapter."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "modules/launcher"
REPO = ROOT.parents[1]


def node():
    return shutil.which("node")


def python():
    # sys.executable may point at the agent host binary instead of Python.
    return shutil.which("python3") or sys.executable


@unittest.skipUnless(node(), "Node is needed to exercise QML's JavaScript logic")
class LauncherLogicTests(unittest.TestCase):
    def evaluate(self, expression):
        source = (LAUNCHER / "Logic.js").read_text()
        result = subprocess.run(
            [node(), "-e", source + "\nconsole.log(JSON.stringify(" + expression + "));"],
            check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout)

    def test_route_understands_actions_calculator_and_app_filters(self):
        self.assertEqual(self.evaluate("route('>')"), {"mode": "actions", "query": ""})
        self.assertEqual(self.evaluate("route('>scheme tokyo')"), {"mode": "scheme", "query": "tokyo"})
        self.assertEqual(self.evaluate("route('>variant')"), {"mode": "variant", "query": ""})
        self.assertEqual(self.evaluate("route('>wallpaper azul')"), {"mode": "wallpaper", "query": "azul"})
        self.assertEqual(self.evaluate("route('>calc 2+2')"), {"mode": "calc", "query": "2+2"})
        self.assertEqual(self.evaluate("route('= (12 + 3) / 5')"), {"mode": "calc", "query": "(12 + 3) / 5"})
        self.assertEqual(self.evaluate("route('12 * (3 + 4)')"), {"mode": "calc", "query": "12 * (3 + 4)"})
        self.assertEqual(self.evaluate("route('  @i firefox')"), {"mode": "apps", "query": "@i firefox"})
        self.assertEqual(self.evaluate("route('música')"), {"mode": "apps", "query": "música"})

    def test_search_folds_accents_case_and_multiple_words(self):
        entries = [
            {"name": "Música", "genericName": "Reproductor de audio"},
            {"name": "Imágenes", "genericName": "Visor de fotos"},
            {"name": "Calculadora", "genericName": "Cuentas rápidas"},
        ]
        self.assertEqual([e["name"] for e in self.evaluate(
            "search(%s, 'MÚSICA', ['name','genericName'])" % json.dumps(entries))], ["Música"])
        self.assertEqual([e["name"] for e in self.evaluate(
            "search(%s, 'imagenes', ['name','genericName'])" % json.dumps(entries))], ["Imágenes"])
        self.assertEqual([e["name"] for e in self.evaluate(
            "search(%s, 'reproductor audio', ['name','genericName'])" % json.dumps(entries))], ["Música"])
        self.assertEqual(self.evaluate(
            "search(%s, 'calculadora', ['name']).length" % json.dumps(entries)), 1)
        self.assertEqual(self.evaluate(
            "search(%s, 'no-existe-ñ', ['name'])" % json.dumps(entries)), [])
        # Prefix matches rank before matches in the middle.
        rows = [{"name": "Vim"}, {"name": "Avim"}, {"name": "Gvim"}]
        self.assertEqual([e["name"] for e in self.evaluate(
            "search(%s, 'vim', ['name'])" % json.dumps(rows))], ["Vim", "Avim", "Gvim"])

    def test_app_search_filters_desktop_entries_and_hidden_apps(self):
        entries = [
            {"name": "Firefox", "id": "firefox", "noDisplay": False, "runInTerminal": False,
             "genericName": "Navegador web", "comment": "Ver sitios", "keywords": ["web", "internet"],
             "startupClass": "firefox", "execString": "firefox %U", "categories": ["Network"]},
            {"name": "Terminal", "id": "terminal", "noDisplay": False, "runInTerminal": True,
             "genericName": "Emulador", "comment": "Órdenes", "keywords": ["shell"],
             "startupClass": "terminal", "execString": "sh", "categories": ["System"]},
            {"name": "Oculto", "id": "hidden", "noDisplay": True, "runInTerminal": False,
             "genericName": "", "comment": "", "keywords": [], "startupClass": "", "execString": ""},
        ]
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@i firefox')" % json.dumps(entries))], ["firefox"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@k internet')" % json.dumps(entries))], ["firefox"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@d sitios')" % json.dumps(entries))], ["firefox"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(" + json.dumps(entries) + ", '@e %U')")], ["firefox"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@w terminal')" % json.dumps(entries))], ["terminal"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@c Network')" % json.dumps(entries))], ["firefox"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@g navegador')" % json.dumps(entries))], ["firefox"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@t')" % json.dumps(entries))], ["terminal"])
        self.assertEqual([e["id"] for e in self.evaluate(
            "appSearch(%s, '@')" % json.dumps(entries))], ["firefox", "terminal"])
        self.assertNotIn("hidden", [e["id"] for e in self.evaluate(
            "appSearch(%s, '')" % json.dumps(entries))])

    def test_calculator_is_bounded_and_never_evaluates_text(self):
        cases = [
            ("1+2*3", "7"), ("(1+2)*3", "9"), ("2^10", "1024"), ("-2^2", "-4"),
            ("2^-3", "0.125"), ("0.1+0.2", "0.3"), ("pi*2", "6.28318530718"),
            ("e", "2.71828182846"), ("4%3", "1"), ("1e3+2", "1002"),
            ("− 5 + 8", "3"), ("(12 + 3) / 5", "3"),
        ]
        for expression, expected in cases:
            result = self.evaluate("calculate(%s)" % json.dumps(expression))
            self.assertTrue(result["valid"], expression)
            self.assertEqual(result["value"], expected, expression)
        invalid = ["", "1+", "1/0", "2 2", "Math.PI", "alert(1)", "process.exit(1)",
                   "1,5+2", "5!", "(" * 20 + "1" + ")" * 20, "1+" * 100]
        for expression in invalid:
            result = self.evaluate("calculate(%s)" % json.dumps(expression))
            self.assertFalse(result["valid"], expression)
            self.assertTrue(result["error"], expression)
        source = (LAUNCHER / "Logic.js").read_text()
        self.assertNotIn("eval(", source)
        self.assertNotIn("new Function", source)
        self.assertNotIn("Function(", source)
        self.assertNotIn("Qalculator", source)

    def test_actions_schemes_and_variants_are_allowlisted(self):
        self.assertEqual(self.evaluate("actionArgv('lock')"), ["wysun", "lock"])
        self.assertEqual(self.evaluate("actionArgv('settings')"), ["wysun", "settings"])
        for injected in ("'sh'", "'notes; touch /tmp/x'", "'__proto__'", "''", "undefined"):
            self.assertEqual(self.evaluate("actionArgv(%s)" % injected), [])
        self.assertEqual(self.evaluate("schemeArgv('dynamic')"),
                         ["wysun", "scheme", "set", "--dynamic"])
        self.assertEqual(self.evaluate("schemeArgv('dynamic-dark')"),
                         ["wysun", "scheme", "set", "--dynamic", "--mode", "dark"])
        self.assertEqual(self.evaluate("schemeArgv('fluent:light')"),
                         ["wysun", "scheme", "set", "fluent:light"])
        self.assertEqual(self.evaluate("schemeArgv('nope')"), [])
        self.assertEqual(self.evaluate("variantArgv('tonalspot')"),
                         ["wysun", "scheme", "set", "--dynamic", "--variant", "tonalspot"])
        self.assertEqual(self.evaluate("variantArgv('not-a-variant')"), [])
        self.assertEqual(self.evaluate("isCurrentScheme('space-black',false,'','space-black','space-black')"), True)
        self.assertEqual(self.evaluate("isCurrentScheme('tokyo',false,'','space-black','tokyo')"), True)
        self.assertEqual(self.evaluate("isCurrentScheme('fluent:dark',false,'','fluent','dark')"), True)
        self.assertEqual(self.evaluate("isCurrentScheme('dynamic-light',true,'light','space-black','space-black')"), True)
        self.assertEqual(self.evaluate("isCurrentScheme('dynamic-dark',true,'light','space-black','space-black')"), False)

    def test_keyboard_index_wraps_without_running_off_the_list(self):
        self.assertEqual(self.evaluate("[nextIndex(0,1,3), nextIndex(2,1,3), nextIndex(0,-1,3), nextIndex(-1,1,3), nextIndex(0,1,0)]"),
                         [1, 0, 2, 1, -1])


class LauncherWiringTests(unittest.TestCase):
    def test_derivatives_keep_the_gpl_notice_and_commit(self):
        commit = "507d66285e9d9fde9330adc64159cfdebb28c19a"
        paths = list((LAUNCHER).rglob("*.qml")) + list((LAUNCHER).rglob("*.js")) + list((LAUNCHER).rglob("*.py")) + [
            ROOT / "services/Apps.qml", ROOT / "services/Actions.qml", ROOT / "services/Schemes.qml",
        ]
        for path in paths:
            text = path.read_text()
            self.assertIn("Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun", text, path)
            self.assertIn(commit, text, path)
        third_party = (REPO / "THIRD_PARTY.md").read_text()
        self.assertIn("apps/shell/modules/launcher/Wrapper.qml", third_party)
        self.assertIn("apps/shell/modules/launcher/backend.py", third_party)
        self.assertIn("utils/scripts/fzf.js", third_party)

    def test_no_caelestia_cli_or_shortcut_module_is_used(self):
        for path in (LAUNCHER).rglob("*"):
            if path.suffix not in (".qml", ".js", ".py") or not path.is_file():
                continue
            text = path.read_text()
            self.assertNotIn('"caelestia"', text, path)
            self.assertNotIn("execDetached([\"caelestia\"", text, path)
            self.assertNotIn("Shortcuts.qml", text, path)
        self.assertNotIn("modules/Shortcuts.qml", (ROOT / "shell.qml").read_text())

    def test_launcher_is_mounted_only_through_the_popout_card_loader(self):
        card = (ROOT / "modules/popouts/PopoutCard.qml").read_text()
        self.assertIn('import "../launcher" as LauncherModule', card)
        self.assertIn("LauncherModule.Wrapper", card)
        self.assertIn('root.controller.surface === "launcher"', card)
        self.assertIn("active: true", card)
        # The launcher must use the shared phase 2 popout state, not a window.
        self.assertIn('supportsSurface', (ROOT / "ShellController.qml").read_text())
        self.assertIn('"launcher"', (ROOT / "ShellController.qml").read_text())

    def test_wallpapers_use_the_public_writer_and_listing_stays_read_only(self):
        schemes = (ROOT / "services/Schemes.qml").read_text()
        self.assertIn('["wysun", "wallpaper", "set", path]', schemes)
        self.assertNotIn("apply_wallpaper", schemes)
        backend = (LAUNCHER / "backend.py").read_text()
        self.assertNotIn("apply_wallpaper", backend)
        self.assertNotIn("select_wallpaper", backend)
        self.assertIn("choices=('list',)", backend)
        self.assertIn("solo lectura", backend)

    def test_shell_entry_points_are_additive_and_keep_the_qt_fallback(self):
        launcher = (REPO / "bin/wysun").read_text()
        self.assertIn("WYSUN_LAUNCHER", launcher)
        self.assertIn("shell_launcher()", launcher)
        self.assertIn("if command == 'toggle' and not args and shell_launcher()", launcher)
        self.assertIn("os.execv", launcher)
        self.assertIn("ORBIT_THEME", (REPO / "apps/wysun/theme_core.py").read_text())
        shell = (REPO / "bin/wysun-shell").read_text()
        self.assertIn("launcher) exec quickshell", shell)
        self.assertIn("call wysunShell toggle launcher", shell)
        self.assertIn("toggle|open", shell)

    def test_interface_is_in_spanish_and_uses_theme_tokens(self):
        text = "".join((LAUNCHER / name).read_text()
                       for name in ("Content.qml", "ContentList.qml", "SearchBar.qml"))
        for label in ("Buscar", "Sin resultados", "Cerrar lanzador"):
            self.assertIn(label, text)
        for path in (LAUNCHER).rglob("*.qml"):
            text = path.read_text()
            self.assertNotIn("caelestia ", text.lower().replace("derivado de caelestia-dots/shell", ""))


class WallpaperBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wysun-launcher-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.config = Path(self.tmp.name) / "config"
        self.walls = Path(self.tmp.name) / "walls"
        self.home.mkdir()
        self.config.mkdir()
        self.walls.mkdir()
        (self.config / "orbit").mkdir()
        self.current = self.home / "actual.png"
        self.current.write_bytes(b"png")
        (self.walls / "azul.jpg").write_bytes(b"jpg")
        (self.walls / "ñandú.webp").write_bytes(b"webp")
        (self.walls / "notas.txt").write_text("no es una imagen")
        (self.walls / "sub").mkdir()
        (self.config / "orbit/environment.json").write_text(json.dumps({
            "wallpaper": {"default": str(self.current), "folders": [str(self.walls)], "monitors": {}},
            "kept": {"unknown": True},
        }))

    def environment(self):
        return {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_STATE_HOME": str(Path(self.tmp.name) / "state"),
            "XDG_DATA_HOME": str(Path(self.tmp.name) / "data"),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }

    def run_backend(self, *args):
        return subprocess.run([python(), str(LAUNCHER / "backend.py"), *args],
                              env=self.environment(), capture_output=True, text=True)

    def test_list_is_sorted_bounded_and_never_writes_settings(self):
        before = (self.config / "orbit/environment.json").read_bytes()
        result = self.run_backend("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual(rows[0]["path"], str(self.current))
        self.assertTrue(rows[0]["current"])
        self.assertFalse(any(row["current"] for row in rows[1:]))
        paths = [row["path"] for row in rows]
        self.assertIn(str(self.walls / "azul.jpg"), paths)
        self.assertIn(str(self.walls / "ñandú.webp"), paths)
        self.assertNotIn(str(self.walls / "notas.txt"), paths)
        self.assertNotIn(str(self.walls / "sub"), paths)
        self.assertEqual(rows, sorted(rows, key=lambda row: (
            not row["current"], row["name"].casefold(), row["path"])))
        self.assertLessEqual(len(rows), 512)
        self.assertEqual((self.config / "orbit/environment.json").read_bytes(), before)
        self.assertEqual(result.stderr, "")

    def test_wallpaper_writes_are_not_exposed(self):
        result = self.run_backend("wallpaper", str(self.walls / "azul.jpg"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)
        self.assertEqual((self.config / "orbit/environment.json").read_text(), json.dumps({
            "wallpaper": {"default": str(self.current), "folders": [str(self.walls)], "monitors": {}},
            "kept": {"unknown": True},
        }))

    def test_invalid_settings_explain_the_failure_without_touching_the_file(self):
        path = self.config / "orbit/environment.json"
        path.write_text("{not json")
        before = path.read_bytes()
        result = self.run_backend("list")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.strip())
        self.assertEqual(path.read_bytes(), before)

    def test_missing_wallpaper_file_is_ignored(self):
        path = self.config / "orbit/environment.json"
        data = json.loads(path.read_text())
        data["wallpaper"]["default"] = str(self.home / "gone.png")
        path.write_text(json.dumps(data))
        result = self.run_backend("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        names = [row["name"] for row in rows]
        self.assertNotIn("gone.png", names)
        self.assertIn("azul.jpg", names)
        self.assertIn("ñandú.webp", names)


if __name__ == "__main__":
    unittest.main()
