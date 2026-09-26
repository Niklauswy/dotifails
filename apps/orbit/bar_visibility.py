#!/usr/bin/env python3
"""Hide Polybar on monitors whose active desktop contains a fullscreen window."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time


EVENTS = (
    "report", "node_state", "node_flag", "node_remove", "node_add",
    "node_transfer", "node_swap", "desktop_focus", "desktop_activate",
    "desktop_transfer", "desktop_swap", "monitor_add", "monitor_remove",
)
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


def has_fullscreen(node):
    if not node or node.get("hidden"):
        return False
    client = node.get("client")
    return bool(
        (client and client.get("state") == "fullscreen")
        or has_fullscreen(node.get("firstChild"))
        or has_fullscreen(node.get("secondChild"))
    )


def fullscreen_monitors(state):
    result = {}
    for monitor in state.get("monitors", []):
        desktop = next((d for d in monitor.get("desktops", [])
                        if d["id"] == monitor["focusedDesktopId"]), {})
        result[monitor["name"]] = has_fullscreen(desktop.get("root"))
    return result


def snapshot():
    data = subprocess.check_output(["bspc", "wm", "-d"], timeout=2,
                                   stderr=subprocess.DEVNULL)
    return json.loads(data)


def discover_bars():
    """Use the IPC socket generation to detect even in-place Polybar restarts."""
    bars = {}
    for socket in (RUNTIME / "polybar").glob("ipc.*.sock"):
        try:
            pid = int(socket.name.split(".")[1])
            proc = Path("/proc") / str(pid)
            if proc.stat().st_uid != os.getuid() or (proc / "comm").read_text().strip() != "polybar":
                continue
            # Only keep routing fields; never log process environments.
            env = dict(item.split(b"=", 1) for item in (proc / "environ").read_bytes().split(b"\0")
                       if item.startswith((b"MONITOR=", b"DISPLAY=")))
            monitor = env.get(b"MONITOR", b"").decode()
            display = env.get(b"DISPLAY", b"").decode()
            if not monitor or display.split(".")[0] != os.environ.get("DISPLAY", "").split(".")[0]:
                continue
            stat = socket.stat()
            bars[pid] = (monitor, stat.st_ino, stat.st_mtime_ns)
        except (OSError, ValueError):
            continue
    return bars


def send(pid, hidden):
    try:
        return subprocess.run(
            ["polybar-msg", "-p", str(pid), "cmd", "hide" if hidden else "show"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class Visibility:
    def __init__(self, sender=send):
        self.applied = {}
        self.sender = sender

    def update(self, state, bars):
        hidden = fullscreen_monitors(state)
        self.applied = {pid: value for pid, value in self.applied.items() if pid in bars}
        for pid, generation in bars.items():
            target = (generation, hidden.get(generation[0], False))
            if self.applied.get(pid) != target and self.sender(pid, target[1]):
                self.applied[pid] = target

    def restore(self):
        for pid, (_, hidden) in self.applied.items():
            if hidden:
                self.sender(pid, False)
        self.applied.clear()


def watch():
    display = re.sub(r"[^a-zA-Z0-9_-]", "_", os.environ.get("DISPLAY", "default"))
    lock_path = RUNTIME / f"orbit-bar-visibility-{display}.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        lock.seek(0)
        lock.truncate()
        lock.write(str(os.getpid()))
        lock.flush()
        stopping = False

        def stop(*_):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        visibility = Visibility()
        try:
            while not stopping:
                subscription = None
                try:
                    subscription = subprocess.Popen(
                        ["bspc", "subscribe", *EVENTS], stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, bufsize=0,
                    )
                    bars = discover_bars()
                    visibility.update(snapshot(), bars)
                    with selectors.DefaultSelector() as selector:
                        selector.register(subscription.stdout, selectors.EVENT_READ)
                        while not stopping:
                            events = selector.select(timeout=2)
                            if events and not os.read(subscription.stdout.fileno(), 65536):
                                break
                            current = discover_bars()
                            # Events are immediate; the quiet-time reconciliation also
                            # retries failed IPC and catches an in-place bar restart.
                            visibility.update(snapshot(), current)
                            bars = current
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass
                finally:
                    if subscription is not None:
                        if subscription.poll() is None:
                            subscription.terminate()
                            try:
                                subscription.wait(timeout=1)
                            except subprocess.TimeoutExpired:
                                subscription.kill()
                                subscription.wait()
                        subscription.stdout.close()
                    # A WM restart or a stopped watcher must not strand a hidden bar.
                    visibility.restore()
                if not stopping:
                    time.sleep(1)
        finally:
            visibility.restore()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="Show routing without changing bars")
    args = parser.parse_args()
    if args.status:
        print(json.dumps({"fullscreen": fullscreen_monitors(snapshot()), "bars": discover_bars()}))
    else:
        watch()
