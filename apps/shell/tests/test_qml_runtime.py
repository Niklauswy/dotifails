"""Offscreen Quickshell probes for the OSD sources.

Brightness is observed through a fake backlight tree (no polling, no hardware);
the stub ``brightnessctl`` only describes it. Skipped without ``quickshell``.
"""
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

SHELL = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("quickshell"), "quickshell no está instalado")
class OsdRuntimeTests(unittest.TestCase):
    def run_probe(self, discovery, trigger=None):
        with tempfile.TemporaryDirectory(prefix="wysun-osd-") as temp:
            root = Path(temp)
            backlight = root / "backlight/fake"
            backlight.mkdir(parents=True)
            (backlight / "brightness").write_text("50\n")
            (backlight / "max_brightness").write_text("100\n")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "brightnessctl"
            stub.write_text("#!/bin/sh\n" + discovery + "\n")
            stub.chmod(0o755)
            run = root / "run"
            run.mkdir(mode=0o700)
            env = {"PATH": str(bin_dir) + ":/usr/bin:/bin", "HOME": str(root / "home"),
                   "XDG_RUNTIME_DIR": str(run), "XDG_STATE_HOME": str(root / "state"),
                   "XDG_CONFIG_HOME": str(root / "config"), "LANG": "C.UTF-8",
                   "QT_QPA_PLATFORM": "offscreen", "WYSUN_BACKLIGHT_ROOT": str(root / "backlight"),
                   "WYSUN_PROBE_SECONDS": "5"}
            process = subprocess.Popen(["quickshell", "-p", str(SHELL / "OsdProbe.qml")], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            lines = []

            def read():
                for line in process.stdout:
                    lines.append(line)
                    if "PROBE_READY" in line and trigger:
                        trigger(backlight)

            reader = threading.Thread(target=read)
            reader.start()
            try:
                process.wait(timeout=30)
            finally:
                if process.poll() is None:
                    process.kill()
                reader.join()
            reader = None
            return re.sub(r"\x1b\[[0-9;]*m", "", "".join(lines))

    def test_backlight_change_shows_osd_and_initial_value_is_ignored(self):
        log = self.run_probe("echo 'fake,backlight,50,50%,100'",
                             lambda backlight: (backlight / "brightness").write_text("80\n"))
        self.assertRegex(log, r"PROBE_READY true fake 50\s+false")
        self.assertNotIn("PROBE_CHANGED 50", log)
        self.assertIn("PROBE_CHANGED 80", log)
        self.assertIn("PROBE_OSD true brightness", log)
        # The window hides itself: no input, no focus, no timer left behind.
        self.assertIn("PROBE_OSD false brightness", log)
        self.assertIn("PROBE_DONE false", log)

    def test_missing_backlight_is_reported_and_never_shows_the_osd(self):
        log = self.run_probe("exit 1")
        self.assertRegex(log, r"PROBE_READY false\s+0 No hay brillo de pantalla disponible false")
        self.assertNotIn("PROBE_OSD true", log)

    def test_absent_pipewire_is_explained_and_silent(self):
        log = self.run_probe("exit 1")
        # No PipeWire daemon in the sandbox: the provider is absent, not a crash.
        self.assertIn("PROBE_AUDIO false false No hay una salida de audio PipeWire", log)
        self.assertNotIn("PROBE_OSD true", log)


if __name__ == "__main__":
    unittest.main()
