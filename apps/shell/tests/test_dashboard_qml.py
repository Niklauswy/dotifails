"""Load the dashboard and the popout morph in Quickshell 0.3.0, offscreen.

Everything runs with a temporary HOME/XDG tree, no session bus and no
compositor: the gallery uses a FloatingWindow (never a PanelWindow) and fixture
providers, except in the "live" case, which proves the real providers degrade
to "No disponible" when MPRIS and Hyprland are absent.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SHELL = Path(__file__).resolve().parents[1]
VARIANTS = [("space-black", "space-black"), ("space-black", "tokyo"), ("space-black", "severance"),
            ("fluent", "light"), ("fluent", "dark")]
ANSI = re.compile(r"\x1b\[[0-9;]*m")
BAD = re.compile(r"(ERROR|TypeError|ReferenceError|is not a type|Binding loop|Unable to assign|Cannot assign|"
                 r"is not installed|Cyclic|undefined is not|Cannot read property)")


def run_gallery(temp, theme, **extra):
    """Run the gallery once; return (log lines, output dir)."""
    shell = temp / "shell"
    if not shell.exists():
        shutil.copytree(SHELL, shell, ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (shell / "qmldir").write_text((shell / "qmldir").read_text() + "DashboardFixtures 1.0 DashboardFixtures.qml\n")
        shutil.copy(SHELL / "tests/DashboardFixtures.qml", shell / "DashboardFixtures.qml")
        shutil.copy(SHELL / "tests/dashboard_gallery.qml", shell / "shell.qml")
    for name in ("cfg/orbit", "state", "run", "out"):
        (temp / name).mkdir(parents=True, exist_ok=True)
    (temp / "run").chmod(0o700)
    env = {k: v for k, v in os.environ.items() if k not in ("DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY", "DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE")}
    env.update(HOME=str(temp), XDG_CONFIG_HOME=str(temp / "cfg"), XDG_STATE_HOME=str(temp / "state"),
               XDG_RUNTIME_DIR=str(temp / "run"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               WYSUN_THEME=theme, WYSUN_GALLERY_OUT=str(temp / "out/shot-%t.png"))
    env.update({"WYSUN_GALLERY_" + key.upper(): str(value) for key, value in extra.items()})
    run = subprocess.run(["quickshell", "-p", str(shell / "shell.qml"), "-n"], env=env, capture_output=True, text=True, timeout=90)
    return [ANSI.sub("", line) for line in (run.stdout + run.stderr).splitlines()], temp / "out"


def tagged(lines, tag):
    return [line.split(tag, 1)[1].strip() for line in lines if tag in line]


def problems(lines):
    # The host has no PanelWindow here, so the mask warning and a missing
    # Hyprland socket are expected; everything else matching BAD is a defect.
    return [line for line in lines if BAD.search(line) and "window masks" not in line]


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is not installed")
class DashboardQmlTests(unittest.TestCase):
    def gallery(self, theme="space-black:tokyo", **extra):
        with tempfile.TemporaryDirectory(prefix="wysun-dash-") as name:
            lines, out = run_gallery(Path(name), theme, **extra)
            shots = {p.name: p.stat().st_size for p in out.glob("*.png")}
            colours = {}
            for path in out.glob("*.png"):
                colours[path.name] = path.read_bytes()
            return lines, shots, colours

    def test_every_tab_renders_in_all_five_themes_without_qml_errors(self):
        digests = {}
        for style, variant in VARIANTS:
            lines, shots, images = self.gallery(style + ":" + variant, tabs="0,1,2,3", fixture="full")
            self.assertEqual(problems(lines), [], style + ":" + variant)
            self.assertIn("0", tagged(lines, "WYSUN_GALLERY_DONE"), "\n".join(lines[-12:]))
            self.assertEqual(sorted(shots), ["shot-%d.png" % i for i in range(4)], variant)
            self.assertTrue(all(size > 8000 for size in shots.values()), shots)
            digests[(style, variant)] = [hash(images["shot-%d.png" % i]) for i in range(4)]
            self.assertEqual(len(set(digests[(style, variant)])), 4, "each tab paints differently")
            texts = [json.loads(t) for t in tagged(lines, "WYSUN_GALLERY_TEXTS")]
            self.assertEqual(len(texts), 4)
            for label in ("Inicio", "Música", "Rendimiento", "Escritorios"):
                self.assertIn(label, texts[0])
            self.assertTrue(any(re.fullmatch(r"\d\d:\d\d", t) for t in texts[0]), "clock")
            self.assertIn("Canción de prueba", texts[1])
            self.assertIn("34%", texts[2])
            self.assertIn("Escritorio 2 · actual", texts[3])
        for index in range(4):
            self.assertEqual(len({digests[v][index] for v in VARIANTS}), 5, "each theme repaints tab %d" % index)

    def test_absent_providers_say_unavailable_instead_of_zero(self):
        lines, shots, _ = self.gallery(tabs="0,1,2,3", fixture="empty")
        self.assertEqual(problems(lines), [])
        texts = [json.loads(t) for t in tagged(lines, "WYSUN_GALLERY_TEXTS")]
        self.assertEqual(len(texts), 4)
        self.assertIn("Sin reproducción", texts[0])
        self.assertIn("Sin reproducción", texts[1])
        self.assertIn("No disponible", texts[2])
        self.assertIn("Temperatura: no disponible", texts[2])
        self.assertIn("No hay escritorios disponibles en esta pantalla.", texts[3])
        for page in texts:
            self.assertFalse([t for t in page if re.fullmatch(r"0\s?%", t)], "an absent sample is never drawn as 0 %")

    def test_live_providers_without_mpris_or_hyprland_degrade_cleanly(self):
        lines, shots, _ = self.gallery(tab=2, live=1, fixture="full")
        self.assertEqual(problems(lines), [], "\n".join(lines[-15:]))
        providers = json.loads(tagged(lines, "WYSUN_GALLERY_PROVIDERS")[0])
        self.assertEqual((providers["workspaces"], providers["windows"]), (0, 0))
        self.assertEqual(providers["media"], {"title": "Sin reproducción", "players": 0})
        self.assertTrue(0 <= providers["cpu"] <= 100 and 0 <= providers["memory"] <= 100)
        self.assertEqual(sorted(shots), ["shot-2.png"])

    def test_interrupted_transition_continues_from_the_current_progress(self):
        lines, shots, _ = self.gallery(scenario="interrupt")
        self.assertEqual(problems(lines), [])
        closed_at = float(tagged(lines, "WYSUN_GALLERY_CLOSE")[0])
        reopened_at = float(tagged(lines, "WYSUN_GALLERY_REOPEN")[0])
        self.assertTrue(0.02 < closed_at < 0.98, closed_at)
        # The close ran for 90 ms: it moved back, but not to zero.
        self.assertTrue(0.0 <= reopened_at < closed_at + 0.001, (closed_at, reopened_at))
        raw = tagged(lines, "WYSUN_GALLERY_SAMPLES")[0]
        samples = json.loads(raw[: raw.index("]") + 1])
        self.assertGreater(len(samples), 10)
        # Timer samples may skip rendered frames under load. Check continuity
        # at the two retargets directly instead of assuming a frame cadence.
        self.assertAlmostEqual(float(tagged(lines, "WYSUN_GALLERY_CLOSE_IMMEDIATE")[0]), closed_at)
        self.assertAlmostEqual(float(tagged(lines, "WYSUN_GALLERY_REOPEN_IMMEDIATE")[0]), reopened_at)
        self.assertEqual(samples[-1], 1)
        self.assertTrue(raw.rstrip().endswith("open"), raw[-30:])
        # Once it has started opening, the close/reopen never fell back to zero.
        started = next(i for i, value in enumerate(samples) if value > 0)
        self.assertGreater(min(samples[started:]), 0.0)

    def test_reduced_motion_swaps_the_morph_for_a_short_fade(self):
        lines, shots, _ = self.gallery(scenario="interrupt", reduced=1)
        self.assertEqual(problems(lines), [])
        raw = tagged(lines, "WYSUN_GALLERY_SAMPLES")[0]
        samples = json.loads(raw[: raw.index("]") + 1])
        self.assertEqual(samples[-1], 1)
        # A 60 ms fade has far fewer intermediate frames than the 320 ms morph.
        self.assertLess(len([s for s in samples if 0 < s < 1]), 14)


if __name__ == "__main__":
    unittest.main()
