#!/usr/bin/env python3
"""Exercise installed Python apps on the runner's private synthetic Hyprland.

Use nested_runtime.py --probe /absolute/path/to/this/file --probe-timeout 180.
WYSUN_TEST_SOURCE selects the integrated checkout for installation if missing;
the installed runner cannot infer that checkout. No compositor/media is started,
no screenshot is taken, and no existing user home or clipboard is accepted.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import uuid


def wait_for(function, description, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = function()
        if value:
            return value
        time.sleep(.1)
    raise RuntimeError("Timeout: " + description)


def peer_pid(path):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(2)
        connection.connect(str(path))
        pid, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != os.getuid():
        raise RuntimeError("Socket belongs to a different user")
    return pid


def private_environment():
    env = dict(os.environ)
    runtime = Path(env.get("XDG_RUNTIME_DIR", "/nonexistent")).resolve()
    run_dir = runtime.parent
    if runtime.name != "r" or run_dir.parent != Path("/tmp") or not run_dir.name.startswith("ws-"):
        raise RuntimeError("Only nested_runtime.py /tmp/ws-*/r is accepted")
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        value = Path(env.get(key, "/nonexistent")).resolve()
        if not value.is_relative_to(run_dir) or value == run_dir or not value.is_dir():
            raise RuntimeError("Expected disposable runner directory: " + key)
    display = env.get("WAYLAND_DISPLAY", "")
    if not display or "/" in display or not (runtime / display).is_socket():
        raise RuntimeError("Expected a private Wayland socket")
    executable = Path(f"/proc/{peer_pid(runtime / display)}/exe").resolve()
    if executable.name != "Hyprland" or not executable.is_relative_to(Path("/tmp")):
        raise RuntimeError("Wayland peer is not the extracted test Hyprland")
    if env.get("DBUS_SYSTEM_BUS_ADDRESS") != "unix:path=" + str(run_dir / "no-system-bus"):
        raise RuntimeError("Host system bus must be disabled")
    if env.get("DBUS_SESSION_BUS_ADDRESS", "").split(",", 1)[0] != "unix:path=" + str(runtime / "bus"):
        raise RuntimeError("Expected the runner's explicit private session bus")
    if Path(f"/proc/{peer_pid(runtime / 'bus')}/exe").resolve().name != "dbus-daemon":
        raise RuntimeError("Unexpected private bus peer")
    for key in ("APPIMAGE", "APPDIR", "ARGV0", "DISPLAY", "PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH", "QT_PLUGIN_PATH"):
        env.pop(key, None)
    env.update(QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="Wysun:Hyprland",
               PYTHONDONTWRITEBYTECODE="1",
               PULSE_SERVER="unix:" + str(runtime / "no-pulse-server"))
    return env, runtime, run_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    env, runtime, run_dir = private_environment()
    home = Path(env["HOME"])
    public = home / ".local/bin/wysun"
    installed = home / ".local/share/orbit/app"
    processes, streams, owned_groups = [], [], set()
    evidence = {"result": "INCOMPLETE", "backend": "installed Python; private native Hyprland",
                "phases": [], "not_tested": ["physical session", "real user data", "rich/image clipboard",
                "paste into another app", "all Notes/Files features", "audio/media", "notifications/lock"]}
    token = "wysun-probe-" + uuid.uuid4().hex[:10]
    output = run_dir / "installed-apps-result.json"

    def command(argv, timeout=15, **kwargs):
        return subprocess.run(list(map(str, argv)), env=env, cwd="/", text=True,
                              capture_output=True, timeout=timeout, check=True, **kwargs).stdout.strip()

    def hypr(*args):
        return json.loads(command(["hyprctl", "-j", *args]))

    def clients():
        return hypr("clients")

    def mapped(title, pid=None):
        return next((w for w in clients() if w.get("title") == title and (pid is None or w.get("pid") == pid)), None)

    def focused(window):
        if window is None:
            return False
        active = hypr("activewindow")
        return active.get("address") == window["address"] and not active.get("xwayland", True)

    def launcher_focused():
        # Qt may create a new Wayland surface/address after hide/show.
        return focused(mapped("Wysun", launcher_pid))

    def notes_window():
        # Qt may append its application display name to the native title.
        return next((w for w in clients() if w.get("pid") == launcher_pid and
                     (w.get("title") == "Wysun Notes" or w.get("title", "").startswith("Wysun Notes — "))), None)

    def key(*values):
        command(["wtype", "-s", "200", *values])

    def chord(modifier, letter):
        key("-M", modifier, "-k", letter, "-m", modifier)

    def query(sql, parameters=()):
        path = home / ".local/share/orbit/orbit.sqlite3"
        if not path.exists():
            return []
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2) as db:
            return db.execute(sql, parameters).fetchall()

    def clipboard():
        try:
            return command(["wl-paste", "--no-newline", "--type", "text/plain"], timeout=3)
        except subprocess.SubprocessError:
            return None

    def start(name, argv, **kwargs):
        stream = (run_dir / ("installed-" + name + ".log")).open("w")
        streams.append(stream)
        process = subprocess.Popen(list(map(str, argv)), env=env, cwd="/", stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True, **kwargs)
        processes.append(process)
        owned_groups.add(process.pid)
        return process

    def phase(name, **details):
        evidence["phases"].append(dict(name=name, **details))
        output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(dict(phase=name, **details)), flush=True)

    try:
        monitors = hypr("monitors")
        if len(monitors) != 1 or monitors[0]["name"] != "WYSUN-TEST-1":
            raise RuntimeError("Only the single synthetic WYSUN-TEST-1 output is accepted")
        if not public.exists() or not installed.is_dir():
            source = Path(env.get("WYSUN_TEST_SOURCE", str(Path(__file__).resolve().parents[3]))).resolve()
            installer = source / "installer/main.py"
            if not installer.is_file():
                raise RuntimeError("Set WYSUN_TEST_SOURCE to the integrated checkout (installer/main.py missing)")
            command(["/usr/bin/python3", installer, "install", "--source", source, "--target-home", home,
                     "--components", "wayland", "--config-only"], timeout=60)
        if not public.resolve().is_relative_to(home) or not installed.resolve().is_relative_to(home):
            raise RuntimeError("Installed public command and application must remain inside disposable HOME")
        # Resolve commands directly; PATH's runner fixture must never stand in for Python.
        env["PATH"] = str(home / ".local/bin") + ":" + env["PATH"]
        for tool in ("hyprctl", "wtype", "wl-copy", "wl-paste"):
            if not shutil.which(tool, path=env["PATH"]):
                raise RuntimeError("Missing runtime test dependency: " + tool + " (extract wl-clipboard in test root; no host installation)")
        env.pop("WYSUN_TEST_SOURCE", None)
        if (runtime / f"orbit-{os.getuid()}.sock").exists():
            raise RuntimeError("Expected no pre-existing Python launcher in this disposable runtime")
        # Seed one synthetic snippet through the real installed data model.
        command(["/usr/bin/python3", "-c",
                 "import sys;sys.path.insert(0,sys.argv[1]);from data_v2 import StoreV2;"
                 "s=StoreV2();s.rich_snippet(sys.argv[2],sys.argv[2],sys.argv[3],'','snippet');s.db.close()",
                 installed, token, "Native snippet {date} " + token])
        began = time.monotonic()
        command([public, "launcher"])
        endpoint = runtime / f"orbit-{os.getuid()}.sock"
        wait_for(endpoint.is_socket, "installed launcher socket")
        launcher_pid = peer_pid(endpoint)
        cmdline = Path(f"/proc/{launcher_pid}/cmdline").read_bytes().split(b"\0")
        if str(installed / "orbit.py").encode() not in cmdline or os.getpgid(launcher_pid) != launcher_pid:
            raise RuntimeError("Launcher is not the installed, separately grouped Python application")
        owned_groups.add(launcher_pid)
        wait_for(lambda: mapped("Wysun", launcher_pid), "native Python launcher mapped")
        wait_for(launcher_focused, "launcher takes keyboard focus")
        phase("launcher_open_focus", elapsed_ms=round((time.monotonic() - began) * 1000, 1), xwayland=False)
        command([public, "launcher"])
        wait_for(lambda: not mapped("Wysun", launcher_pid), "public toggle closes launcher")
        command([public, "launcher"])
        wait_for(launcher_focused, "public toggle reopens with focus")
        key("6*7", "-s", "200", "-k", "Return")
        wait_for(lambda: query("SELECT result FROM history WHERE query=?", ("6*7",)) == [("42",)], "calculator records real result")
        wait_for(lambda: clipboard() == "42", "calculator copies result through native clipboard")
        phase("launcher_toggle_keyboard_calculator", expression="6*7", result="42", persisted=True, clipboard=True)
        command([public, "snippets"])
        wait_for(launcher_focused, "snippet launcher focus")
        key(token, "-s", "200", "-k", "Return")
        expected = "Native snippet " + datetime.date.today().isoformat() + " " + token
        wait_for(lambda: clipboard() == expected, "snippet expands date and copies")
        wait_for(lambda: query("SELECT uses FROM snippets WHERE shortcut=?", (token,)) == [(1,)], "snippet usage persists")
        phase("snippet_search_expand_copy", seeded=True, activated_by="native keyboard", persisted_use=True)
        # App is hidden: capture must come from the native data-control watcher.
        wait_for(lambda: not mapped("Wysun", launcher_pid), "launcher hidden after snippet copy")
        # The app deliberately suppresses its own copy events for 150 ms.
        # Start the external offer after that documented suppression window.
        time.sleep(.25)
        external = token + " external clipboard"
        owner = start("clipboard-owner", ["wl-copy", "--foreground", "--type", "text/plain"], stdin=subprocess.PIPE)
        owner.stdin.write(external.encode()); owner.stdin.close()
        wait_for(lambda: query("SELECT text FROM clips WHERE text=?", (external,)), "unfocused native clipboard history capture")
        command([public, "clipboard"])
        wait_for(launcher_focused, "clipboard UI focus")
        key(token, "-s", "250", "-k", "Return")
        wait_for(lambda: clipboard() == external and not mapped("Wysun", launcher_pid), "clipboard search/copy closes launcher")
        phase("clipboard_capture_search_copy", unfocused_capture=True, source="wl-copy on private output", text_only=True)
        command([public, "notes"])
        notes = wait_for(notes_window, "Notes native window")
        wait_for(lambda: focused(notes), "Notes keyboard focus")
        chord("ctrl", "n")
        chord("ctrl", "a")
        body = "# " + token + "\n\nSaved by native keyboard.\n"
        key(body)
        chord("ctrl", "s")
        notes_dir = home / ".local/share/orbit/notes"
        wait_for(lambda: any(p.read_text() == body for p in notes_dir.glob("*.md")), "Notes Markdown saved by Ctrl+S")
        key("-k", "Escape")
        wait_for(lambda: not notes_window(), "Notes Escape closes")
        command([public, "notes"])
        wait_for(notes_window, "Notes reopens with saved local data")
        key("-k", "Escape")
        wait_for(lambda: not notes_window(), "Notes cleanup close")
        phase("notes_create_save_reopen", markdown_exact=True, keyboard="Ctrl+N/Ctrl+A/type/Ctrl+S/Escape")
        folder = home / "Documents" / token
        destination = folder / "destination"
        destination.mkdir(parents=True)
        files = start("files", [public, "files", folder])
        def files_window():
            return next((w for w in clients() if w.get("pid") == files.pid and "Wysun Files" in w.get("title", "")), None)
        window = wait_for(files_window, "installed Files opens supplied synthetic folder")
        wait_for(lambda: focused(window), "Files keyboard focus")
        key("-M", "ctrl", "-M", "shift", "-k", "n", "-m", "shift", "-m", "ctrl")
        wait_for(lambda: mapped("Nueva carpeta", files.pid), "Files new-folder dialog")
        key("created-at-source", "-k", "Return")
        wait_for(lambda: (folder / "created-at-source").is_dir(), "Files creates folder through GUI")
        chord("ctrl", "l")
        key(str(destination), "-k", "Return")
        wait_for(lambda: any(w.get("pid") == files.pid and w.get("title", "").startswith("destination") for w in clients()), "Files navigates by Ctrl+L")
        key("-M", "ctrl", "-M", "shift", "-k", "n", "-m", "shift", "-m", "ctrl")
        wait_for(lambda: mapped("Nueva carpeta", files.pid), "Files destination new-folder dialog")
        key("created-at-destination", "-k", "Return")
        wait_for(lambda: (destination / "created-at-destination").is_dir(), "Files action applies in navigated folder")
        chord("ctrl", "w")
        wait_for(lambda: files.poll() is not None, "Files last tab closes window and process")
        if files.returncode:
            raise RuntimeError("Files exited with code " + str(files.returncode))
        phase("files_open_navigate_mkdir_close", directories_created=2, keyboard=True, native=True)
        from rich_clipboard_probe import run_rich_clipboard
        rich = run_rich_clipboard(env, launcher_pid)
        phase("rich_clipboard_native_roundtrip", result=rich["result"], formats=[item["kind"] for item in rich["phases"]])
        evidence["not_tested"].remove("rich/image clipboard")
        evidence["result"] = "WYSUN_INSTALLED_APPS_NATIVE_OK"
    except Exception as error:
        evidence["error"] = type(error).__name__ + ": " + str(error)
        evidence["failure_compositor_state"] = {}
        for request in ("clients", "activewindow"):
            try:
                evidence["failure_compositor_state"][request] = hypr(request)
            except Exception as diagnostic_error:
                evidence["failure_compositor_state"][request] = {"diagnostic_error": str(diagnostic_error)}
        # Only the guarded synthetic compositor is queried; persist before
        # terminating any app so failure evidence still contains its windows.
        output.write_text(json.dumps(evidence, indent=2) + "\n")
        raise
    finally:
        # Groups are either our Popen children or verified installed orbit.py.
        for group in reversed(sorted(owned_groups)):
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for process in processes:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=2)
        # The public launcher forks its own group; ensure its watcher exits too.
        for group in owned_groups:
            try:
                os.killpg(group, 0)
            except ProcessLookupError:
                continue
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for stream in streams:
            stream.close()
        output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
