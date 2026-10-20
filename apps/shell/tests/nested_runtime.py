#!/usr/bin/env python3
"""Run the real shell in a private Labwc headless -> Hyprland test session.

No package installation, screenshots, physical input, host bus, audio, autostart,
or active-session services. Run only after coordinating the serial GPU slot.
The optional --root is a dpkg-deb extraction, not a system installation.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import tempfile
import time

SHELL = Path(__file__).resolve().parents[1]


def wait_for(predicate, description, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise RuntimeError("Timed out: " + description)


def stop_owned_group(process):
    """Every tracked process was started with start_new_session=True.

    start-hyprland forks its child in the same group and pins parent death to
    SIGKILL. Signal the group, not only the watchdog, and tolerate an exit race.
    """
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--hypr-config", type=Path, required=True)
    parser.add_argument("--probe", type=Path, help="Run a Python probe with the private live compositor environment before cleanup")
    parser.add_argument("--probe-only", action="store_true", help="Run the probe after compositor/output setup, skipping shell tests")
    parser.add_argument("--probe-timeout", type=int, default=60, help="Probe deadline in seconds (1-180)")
    parser.add_argument("--coordinated", action="store_true", help="Confirm the serial compositor slot is reserved")
    args = parser.parse_args()
    if not args.coordinated:
        parser.error("Reserve the compositor slot with the integrator, then pass --coordinated")
    if args.probe_only and not args.probe:
        parser.error("--probe-only requires --probe")
    if not 1 <= args.probe_timeout <= 180:
        parser.error("--probe-timeout must be between 1 and 180 seconds")
    if list(Path("/dev/dri").glob("card*")) or Path("/dev/input").exists():
        parser.error("Use bwrap with a private /dev exposing only renderD128; physical DRM/input nodes must be hidden")
    prefix = args.root.resolve()
    lib = prefix / "usr/lib/x86_64-linux-gnu"
    binary = prefix / "usr/bin"
    processes, streams = [], []
    run_dir = Path(tempfile.mkdtemp(prefix="ws-"))
    print("Isolated diagnostics:", run_dir, flush=True)
    paths = {name: run_dir / ("r" if name == "runtime" else name) for name in ("home", "runtime", "config", "cache", "data", "state", "bin")}
    for path in paths.values():
        path.mkdir(mode=0o700)
    env = {
        "HOME": str(paths["home"]), "XDG_RUNTIME_DIR": str(paths["runtime"]),
        "XDG_CONFIG_HOME": str(paths["config"]), "XDG_CACHE_HOME": str(paths["cache"]),
        "XDG_DATA_HOME": str(paths["data"]), "XDG_STATE_HOME": str(paths["state"]),
        "PATH": str(paths["bin"]) + ":" + str(binary) + ":/usr/bin:/bin",
        "LD_LIBRARY_PATH": str(lib) + ":" + str(lib / "weston"),
        "QML_IMPORT_PATH": str(lib / "qt6/qml"), "QT_QPA_PLATFORM": "wayland",
        "QT_QUICK_BACKEND": "software", "QS_NO_RELOAD_POPUP": "1",
        "XDG_DATA_DIRS": str(prefix / "usr/share") + ":/usr/share",
        "XDG_CURRENT_DESKTOP": "Hyprland", "XDG_SESSION_TYPE": "wayland",
        "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=" + str(run_dir / "no-system-bus"),
        "LANG": "C.UTF-8", "USER": "wysun-test", "LOGNAME": "wysun-test",
        "HYPRLAND_NO_SD_NOTIFY": "1", "HYPRLAND_NO_RT": "1",
        "WLR_BACKENDS": "headless", "WLR_HEADLESS_OUTPUTS": "1",
        "WLR_LIBINPUT_NO_DEVICES": "1", "WLR_RENDERER": "gles2",
        "WLR_RENDER_DRM_DEVICE": "/dev/dri/renderD128", "WLR_XWAYLAND": "/bin/false",
    }
    if os.environ.get("WYSUN_TEST_SOURCE"):
        env["WYSUN_TEST_SOURCE"] = os.environ["WYSUN_TEST_SOURCE"]
    # This CLI fixture proves routing only; it is never evidence for Python UI.
    (paths["bin"] / "wysun").write_text(
        "#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\n"
        "p=Path(os.environ['XDG_STATE_HOME'])/'dispatch.json'\n"
        "p.write_text(json.dumps(sys.argv[1:]))\n"
    )
    (paths["bin"] / "wysun").chmod(0o700)
    config = args.hypr_config.read_text()
    autostart = 'hl.on("hyprland.start", function () hl.exec_cmd("wysun-session-services") end)'
    if config.count(autostart) != 1:
        raise RuntimeError("Expected exactly one known session-services autostart; inspect fixture sanitizer")
    config = config.replace(autostart, "-- Session services disabled in isolated runtime test.")
    config += '\nhl.config({ xwayland = { enabled = false }, animations = { enabled = false } })\n'
    config += 'hl.monitor({output="WYSUN-TEST-1",mode="1280x800@60",position="auto",scale=1})\n'
    fixture_config = run_dir / "hyprland.lua"
    fixture_config.write_text(config)

    def command(argv, check=True):
        return subprocess.run([str(x) for x in argv], env=env, text=True, capture_output=True, timeout=10, check=check)

    def start(name, argv):
        stream = (run_dir / (name + ".log")).open("w")
        streams.append(stream)
        process = subprocess.Popen([str(x) for x in argv], env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        return process

    def ipc(method, *values):
        return command([binary / "quickshell", "ipc", "-p", SHELL, "call", "wysunShell", method, *values]).stdout.strip()

    def hypr(*argv):
        return command([binary / "hyprctl", *argv]).stdout.strip()

    def topology():
        try:
            return json.loads(hypr("-j", "monitors"))
        except (subprocess.SubprocessError, ValueError):
            return None

    def layers():
        def walk(value):
            if isinstance(value, dict):
                return ([value] if "namespace" in value else []) + [n for child in value.values() for n in walk(child)]
            return [n for child in value for n in walk(child)] if isinstance(value, list) else []
        return walk(json.loads(hypr("-j", "layers")))

    def namespaces():
        return [layer["namespace"] for layer in layers()]

    def state():
        try:
            return json.loads(ipc("status"))
        except (subprocess.SubprocessError, ValueError):
            return None

    try:
        # Private bus has no host services or activation environment to mutate.
        bus = subprocess.Popen(["/usr/bin/dbus-daemon", "--session", "--nofork", "--address=unix:path=" + str(paths["runtime"] / "bus"), "--print-address=1"], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        processes.append(bus)
        env["DBUS_SESSION_BUS_ADDRESS"] = bus.stdout.readline().strip()
        if not env["DBUS_SESSION_BUS_ADDRESS"]:
            raise RuntimeError("Private D-Bus could not create a socket (sandbox restriction)")
        verified = command([binary / "Hyprland", "--verify-config", "-c", fixture_config], check=False)
        (run_dir / "config-check.log").write_text(verified.stdout + verified.stderr)
        if verified.returncode:
            raise RuntimeError("Hyprland configuration check failed: " + verified.stdout[-1500:] + verified.stderr[-500:])
        print("Hyprland Lua config verified", flush=True)
        parent_config = run_dir / "labwc"
        parent_config.mkdir()
        (parent_config / "rc.xml").write_text('<labwc_config><core><xwaylandPersistence>no</xwaylandPersistence></core></labwc_config>')
        parent = start("labwc", [binary / "labwc", "-C", parent_config])
        parent_sockets = wait_for(lambda: [p for p in paths["runtime"].glob("wayland-*") if p.is_socket()] if parent.poll() is None else None, "Labwc headless socket")
        parent_socket = parent_sockets[0].name
        env["WAYLAND_DISPLAY"] = parent_socket
        watchdog = start("hyprland", [binary / "start-hyprland", "--path", binary / "Hyprland", "--", "-c", fixture_config])
        sockets = wait_for(lambda: [p for p in paths["runtime"].glob("wayland-*") if p.is_socket() and p.name != parent_socket] if watchdog.poll() is None else None, "Hyprland nested socket")
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(3)
            peer.connect(str(sockets[0]))
            compositor_pid, compositor_uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if (compositor_uid != os.getuid()
                or Path(f"/proc/{compositor_pid}/exe").resolve() != (binary / "Hyprland").resolve()
                or os.getpgid(compositor_pid) != watchdog.pid):
            raise RuntimeError("Nested socket peer is not the extracted Hyprland child in our watchdog process group")
        print("Private compositor processes:", {"watchdog_pid": watchdog.pid, "compositor_pid": compositor_pid}, flush=True)
        signatures = wait_for(lambda: list((paths["runtime"] / "hypr").glob("*/.socket.sock")), "Hyprland IPC")
        env["HYPRLAND_INSTANCE_SIGNATURE"] = signatures[0].parent.name
        env["WAYLAND_DISPLAY"] = sockets[0].name
        print("Hyprland initial outputs:", hypr("-j", "monitors", "all"), flush=True)
        print("Create synthetic output:", hypr("output", "create", "headless", "WYSUN-TEST-1"), flush=True)
        monitors = wait_for(topology, "Hyprland enabled output")
        print("Hyprland output:", [m["name"] for m in monitors], flush=True)
        errors = hypr("configerrors")
        if errors and errors != "ok":
            raise RuntimeError("Hyprland runtime config errors: " + errors)
        if args.probe_only:
            subprocess.run(["/usr/bin/python3", str(args.probe.resolve())], env=env, check=True, timeout=args.probe_timeout)
            return
        loaded_at = time.monotonic()
        shell = start("shell", [binary / "quickshell", "--no-duplicate", "-p", SHELL, "--no-color"])
        initial = wait_for(state, "Quickshell IPC after QML load")
        load_ms = round((time.monotonic() - loaded_at) * 1000, 1)
        wait_for(lambda: state() and all(state()["screens"]) and state()["workspaceCount"] > 0, "real Quickshell screen and workspace models")
        initial = state()
        wait_for(lambda: "wysun-bar" in namespaces() and "wysun-desktop" in namespaces(), "bar and desktop layers mapped")
        print("Quickshell layers mapped:", namespaces(), flush=True)
        durations = []
        for surface in ("menu", "windows", "session"):
            before = time.monotonic()
            assert ipc("open", surface) == "true"
            wait_for(lambda: state()["surface"] == surface, surface + " open")
            durations.append(round((time.monotonic() - before) * 1000, 1))
            ipc("close")
        # This socket and output were created by this test. Never pass the
        # caller's WAYLAND_DISPLAY or capture any physical desktop output.
        ipc("open", "menu")
        time.sleep(.2)
        command([binary / "grim", "-o", "WYSUN-TEST-1", run_dir / "synthetic-shell.png"])
        assert (run_dir / "synthetic-shell.png").stat().st_size > 1000
        # Virtual keyboard is connected only to the nested compositor's socket.
        ipc("open", "menu")
        command([binary / "wtype", "-s", "200", "-k", "Escape"])
        wait_for(lambda: state()["surface"] == "", "Escape closes surface")
        ipc("open", "menu")
        command([binary / "wtype", "-s", "200", "notas", "-k", "Return"])
        dispatch_file = paths["state"] / "dispatch.json"
        wait_for(dispatch_file.exists, "public application dispatch")
        assert json.loads(dispatch_file.read_text()) == ["notes"]
        ipc("close")
        # Initial session focus is lock; Tab must reach the next real control.
        # Only the private argv fixture runs, never an actual power command.
        ipc("open", "session")
        command([binary / "wtype", "-s", "200", "-k", "Tab", "-k", "space"])
        wait_for(lambda: json.loads(dispatch_file.read_text()) == ["power"], "Tab moves focus to power control and Space activates it")
        wait_for(lambda: state()["surface"] == "", "keyboard action closes surface")
        # Real Wayland windows, discovered through the target compositor's IPC.
        fixture = run_dir / "fixture"
        fixture.mkdir()
        (fixture / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
    FloatingWindow {
        title: "Wysun synthetic one"
        visible: true
        implicitWidth: 360; implicitHeight: 240
        color: "#15272e"
        Text { anchors.centerIn: parent; text: "Synthetic window"; color: "#d2e4e8" }
    }
    FloatingWindow {
        title: "Wysun synthetic two"
        visible: true
        implicitWidth: 360; implicitHeight: 240
        color: "#211b2e"
        Text { anchors.centerIn: parent; text: "Second synthetic window"; color: "#e5dcfa" }
    }
}''')
        start("fixture", [binary / "quickshell", "-p", fixture, "--no-color"])
        wait_for(lambda: state()["windowCount"] == 2, "synthetic toplevels discovered")
        hypr("dispatch", 'hl.dsp.focus({window="title:Wysun synthetic two"})')
        ipc("open", "windows")
        command([binary / "wtype", "-s", "200", "one", "-k", "Return"])
        wait_for(lambda: state()["surface"] == "", "window selected with Enter")
        active = json.loads(hypr("-j", "activewindow"))
        assert active["title"] == "Wysun synthetic one", active
        hypr("dispatch", 'hl.dsp.window.fullscreen({mode="fullscreen",action="set"})')
        wait_for(lambda: state()["fullscreenMonitors"], "fullscreen event updates shell")
        wait_for(lambda: "wysun-bar" not in namespaces(), "bar hidden on fullscreen monitor")
        ipc("open", "menu")
        wait_for(lambda: "wysun-surface" in namespaces(), "menu can open above fullscreen")
        command([binary / "wtype", "-s", "200", "-k", "Escape"])
        hypr("dispatch", 'hl.dsp.window.fullscreen({mode="fullscreen",action="unset"})')
        wait_for(lambda: "wysun-bar" in namespaces(), "bar restored after fullscreen")
        hypr("output", "create", "headless", "WYSUN-TEST-2")
        wait_for(lambda: "WYSUN-TEST-2" in state()["screens"], "hotplug creates second screen")
        hypr("dispatch", 'hl.dsp.focus({monitor="WYSUN-TEST-2"})')
        ipc("open", "menu")
        wait_for(lambda: state()["monitor"] == "WYSUN-TEST-2", "popup follows focused output")
        hypr("output", "remove", "WYSUN-TEST-2")
        wait_for(lambda: "WYSUN-TEST-2" not in state()["screens"] and state()["surface"] == "", "hot-unplug closes popup")
        # Preferences are synthetic, but loading and inotify delivery are real.
        orbit_config = paths["config"] / "orbit"
        orbit_config.mkdir(exist_ok=True)
        (orbit_config / "theme.json").write_text('{"id":"tokyo"}')
        ipc("reloadPreferences")
        wait_for(lambda: state()["theme"] == "tokyo", "theme event")
        (orbit_config / "theme.json").write_text('{"id":"space-black"}')
        wait_for(lambda: state()["theme"] == "space-black", "theme inotify event")
        (orbit_config / "hypr-bar.json").write_text(json.dumps({"height": 44, "opacity": 80, "background": "#101012", "accent": "#ceced4", "left": ["orbit", "title"], "center": ["workspaces"], "right": ["date", "notifications", "power"]}))
        ipc("reloadPreferences")
        wait_for(lambda: state()["nativeBar"] and state()["bar"]["height"] == 44, "native bar preference contract")
        (orbit_config / "hypr-bar.json").write_text('{"height":24}')
        wait_for(lambda: any(layer["namespace"] == "wysun-bar" and layer["h"] == 24 for layer in layers()), "minimum bar height applied to real layer")
        (orbit_config / "hypr-bar.json").write_text('{"height":40,"background":"#17131f","opacity":100}')
        wait_for(lambda: state()["bar"]["height"] == 40 and state()["bar"]["background"] == "#ff17131f", "native bar inotify event")
        time.sleep(.5)
        log = (run_dir / "shell.log").read_text()
        bad = [line for line in log.splitlines() if any(x in line for x in ("ERROR:", "ReferenceError", "TypeError", "Binding loop", "Cannot assign", "Unable to assign", "is not a function"))]
        assert not bad, "QML diagnostics: " + "\n".join(bad)
        stat = Path(f"/proc/{shell.pid}/stat").read_text().split()
        ticks_before = int(stat[13]) + int(stat[14])
        before = time.monotonic()
        time.sleep(3)
        stat = Path(f"/proc/{shell.pid}/stat").read_text().split()
        cpu = 100 * ((int(stat[13]) + int(stat[14]) - ticks_before) / os.sysconf("SC_CLK_TCK")) / (time.monotonic() - before)
        memory = next(line for line in Path(f"/proc/{shell.pid}/status").read_text().splitlines() if line.startswith("VmRSS:"))
        print(json.dumps({"evidence": "real nested runtime; synthetic preferences and CLI fixture", "screens": initial["screens"],
                          "load_ms": load_ms, "ipc_open_ms": durations, "cpu_one_core_percent_3s": round(cpu, 2), "memory": memory,
                          "keyboard_escape": True, "keyboard_search_dispatch": "notes", "theme_file_events": True,
                          "keyboard_tab_dispatch": "power fixture only",
                          "native_window_activation": True, "fullscreen": True, "monitor_hotplug": True}), flush=True)
        if args.probe:
            subprocess.run(["/usr/bin/python3", str(args.probe.resolve())], env=env, check=True, timeout=args.probe_timeout)
    finally:
        for process in reversed(processes):
            stop_owned_group(process)
        for stream in streams:
            stream.close()


if __name__ == "__main__":
    main()
