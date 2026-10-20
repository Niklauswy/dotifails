#!/usr/bin/env python3
"""Reproducible captures of the phase-4 gallery (notifications, quick settings,
session menu and OSD) in every Wysun style and Material You mode.

Everything runs in a throw-away HOME/XDG tree with an offscreen Qt platform and
fixture data: no compositor, no bars, no D-Bus, no devices and no change to the
real ``~/.local/state/wysun/scheme.json``. Needs ``quickshell`` and Pillow
(Pillow only for the synthetic Material You wallpaper).

Usage: python3 apps/shell/tools/capture_notif_osd.py OUTPUT_DIR
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SHELL = Path(__file__).resolve().parents[1]
APPS = SHELL.parent / "wysun"
FIXED = ("space-black", "tokyo", "severance", "fluent:light", "fluent:dark")


def load(name):
    sys.path.insert(0, str(APPS))
    spec = importlib.util.spec_from_file_location(name, APPS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def environment(root, theme, output, reduced):
    run = root / "run"
    run.mkdir(mode=0o700, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root / "home"),
           "XDG_RUNTIME_DIR": str(run), "XDG_STATE_HOME": str(root / "home/.local/state"),
           "XDG_CONFIG_HOME": str(root / "home/.config"), "XDG_CACHE_HOME": str(root / "cache"),
           "LANG": "C.UTF-8", "QT_QPA_PLATFORM": "offscreen", "WYSUN_GALLERY_OUTPUT": str(output)}
    if theme:
        env["WYSUN_THEME"] = theme
    if reduced:
        env["WYSUN_REDUCED_MOTION"] = "1"
    return env


def capture(root, theme, output, reduced=False):
    result = subprocess.run(["quickshell", "-p", str(SHELL / "NotifOsdGallery.qml")],
                            env=environment(root, theme, output, reduced), capture_output=True,
                            text=True, timeout=60)
    ok = output.is_file() and "WYSUN_GALLERY_CAPTURE true" in result.stdout + result.stderr
    print(("ok   " if ok else "FAIL ") + output.name)
    if not ok:
        print(result.stdout + result.stderr)
    return ok


def main(argv):
    if len(argv) != 2 or shutil.which("quickshell") is None:
        print(__doc__)
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    good = True
    with tempfile.TemporaryDirectory(prefix="wysun-f4-") as temp:
        root = Path(temp)
        (root / "home").mkdir()
        for theme in FIXED:
            good &= capture(root, theme, out / (theme.replace(":", "-") + ".png"))
        good &= capture(root, "space-black", out / "space-black-reduced-motion.png", reduced=True)
        try:
            from PIL import Image
        except ImportError:
            print("Pillow no está instalado: se omiten las capturas Material You")
            return 0 if good else 1
        scheme = load("wysun_scheme")
        core = load("theme_core")
        wallpaper = root / "wallpaper.png"
        image = Image.new("RGB", (128, 128))
        image.putdata([(40 + x, 90 + y // 2, 160 - x // 2) for y in range(128) for x in range(128)])
        image.save(wallpaper)
        for mode in ("dark", "light"):
            core.write_scheme(scheme.generate_dynamic(wallpaper, mode, "tonalspot"), root / "home")
            good &= capture(root, None, out / ("material-you-" + mode + ".png"))
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
