#!/usr/bin/env python3
"""Real rich clipboard between disposable Qt Wayland apps and installed history.

Called by installed_apps_probe after Notes/Files. Child roles below are actual
Qt applications: no clipboard, data-control, history, or OCR mock is used.
Only the guarded /tmp/ws-*/r compositor and temporary HOME are accepted.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

from installed_apps_probe import peer_pid, private_environment, wait_for


def qt_role(role, token):
    env, runtime, run_dir = private_environment()
    # HOME is validated before any Qt/application data module is imported.
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData, QUrl, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QShortcut
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
    app = QApplication([])
    app.setApplicationName("wysun-clipboard-" + role)
    app.setDesktopFileName("wysun-clipboard-" + role)
    window = QWidget(); window.setWindowTitle("Wysun clipboard " + role + " " + token)
    window.resize(420, 240)
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel("Synthetic clipboard " + role + "\n" + token))
    clipboard = app.clipboard()
    folder = Path(env["HOME"]) / "Documents" / token
    files = [folder / "fixture one.txt", folder / "fixture-two.txt"]
    plain = token + " & native HTML"
    html = "<p><strong>" + token + "</strong> &amp; native HTML</p>"
    def publish(name, report):
        target = run_dir / name
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(report)); temporary.replace(target)
    if role == "source":
        import random
        folder.mkdir(parents=True, exist_ok=True)
        for index, path in enumerate(files): path.write_text("Synthetic local file " + str(index) + "\n")
        image = QImage(1024, 512, QImage.Format_RGB32); image.fill(QColor("white"))
        painter = QPainter(image); painter.fillRect(10, 10, 20, 20, QColor("#315787"))
        painter.setPen(QColor("black")); painter.setFont(QFont("DejaVu Sans", 48))
        painter.drawText(60, 100, "MYWYSUN42")
        # Incompressible synthetic area exercises the real >256KiB pipe drain.
        noise_data = random.Random(42).randbytes(512 * 256 * 4)
        noise = QImage(noise_data, 512, 256, 512 * 4, QImage.Format_RGB32)
        painter.drawImage(400, 240, noise); painter.end()
        data = QByteArray(); buffer = QBuffer(data); buffer.open(QIODevice.WriteOnly)
        if not image.save(buffer, "PNG"): raise RuntimeError("Cannot encode synthetic PNG")
        png = bytes(data)
        if len(png) <= 256 * 1024: raise RuntimeError("Synthetic PNG did not exceed drain regression threshold")
        (run_dir / "rich-fixture.png").write_bytes(png)
        generation = 0
        def offer(kind):
            nonlocal generation
            mime = QMimeData()
            if kind == "image": mime.setImageData(image); mime.setData("image/png", png)
            elif kind == "files":
                urls = [QUrl.fromLocalFile(str(path)) for path in files]
                mime.setUrls(urls)
                mime.setData("x-special/gnome-copied-files", ("cut\n" + "\n".join(url.toString() for url in urls)).encode())
                mime.setData("application/x-kde-cutselection", b"1")
            elif kind == "html": mime.setText(plain); mime.setHtml(html)
            else: mime.setText("Neutral clipboard replacement")
            clipboard.setMimeData(mime); generation += 1
            publish("rich-source.json", dict(kind=kind, generation=generation, png_bytes=len(png)))
        for number, kind in enumerate(("neutral", "image", "files", "html")):
            button = QPushButton(kind + " · Alt+" + str(number)); layout.addWidget(button)
            button.clicked.connect(lambda _=False, value=kind: offer(value))
            QShortcut(QKeySequence("Alt+" + str(number)), window).activated.connect(lambda value=kind: offer(value))
    else:
        def receive():
            mime = clipboard.mimeData()
            if mime is None: raise RuntimeError("Native receiver has no clipboard offer")
            report = dict(formats=mime.formats(), text=mime.text(), html=mime.html(),
                          paths=[url.toLocalFile() for url in mime.urls()],
                          gnome=bytes(mime.data("x-special/gnome-copied-files")).decode("utf8", errors="replace"),
                          kde=bytes(mime.data("application/x-kde-cutselection")).decode("ascii", errors="replace"))
            raw = bytes(mime.data("image/png"))
            if raw:
                image = QImage.fromData(raw, "PNG")
                if image.isNull(): raise RuntimeError("Native PNG offer cannot be decoded")
                color = image.pixelColor(15, 15)
                report["image"] = dict(width=image.width(), height=image.height(), rgb=[color.red(), color.green(), color.blue()])
            publish("rich-receiver.json", report)
        button = QPushButton("Read native clipboard · Ctrl+R"); layout.addWidget(button)
        button.clicked.connect(receive)
        QShortcut(QKeySequence("Ctrl+R"), window).activated.connect(receive)
    window.show()
    raise SystemExit(app.exec())


def run_rich_clipboard(env, launcher_pid):
    checked, runtime, run_dir = private_environment()
    for variable in ("HOME", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
        if env.get(variable) != checked.get(variable):
            raise RuntimeError("Rich clipboard environment differs from guarded runner: " + variable)
    home = Path(env["HOME"])
    if peer_pid(runtime / f"orbit-{os.getuid()}.sock") != launcher_pid:
        raise RuntimeError("Rich probe launcher peer changed")
    public = home / ".local/bin/wysun"
    token = "rich-" + uuid.uuid4().hex[:10]
    folder = home / "Documents" / token
    paths = [str(folder / "fixture one.txt"), str(folder / "fixture-two.txt")]
    plain = token + " & native HTML"
    processes, logs = [], []
    report = dict(result="INCOMPLETE", evidence="real private Wayland Qt clipboard; installed history; real extracted Tesseract", phases=[])
    result_path = run_dir / "rich-clipboard-result.json"
    wrapper = home / ".local/bin/tesseract"
    if not wrapper.parent.resolve().is_relative_to(home):
        raise RuntimeError("Disposable OCR launcher parent escapes HOME")
    if wrapper.is_symlink() or (wrapper.exists() and not wrapper.is_file()):
        raise RuntimeError("Disposable OCR launcher must be a regular file, never a symlink")
    original = wrapper.read_bytes() if wrapper.is_file() else None
    original_mode = wrapper.stat().st_mode & 0o777 if wrapper.exists() else None
    wrapper_changed = False
    root = Path("/tmp/wysun-portal-tools/root")
    binary = root / "usr/bin/tesseract"
    tessdata = root / "usr/share/tesseract-ocr/5/tessdata"

    def command(argv, **kwargs):
        return subprocess.run(list(map(str, argv)), env=env, cwd="/", check=True, capture_output=True,
                              text=True, timeout=10, **kwargs).stdout.strip()

    def hypr(request): return json.loads(command(["hyprctl", "-j", request]))
    def key(*args): command(["wtype", "-s", "200", *args])
    def mapped(pid, title=None):
        return next((w for w in hypr("clients") if w.get("pid") == pid and (title is None or w.get("title") == title)), None)

    def focus(pid, title):
        window = wait_for(lambda: mapped(pid, title), "rich native window: " + title)
        if window.get("xwayland", True) or not re.fullmatch(r"0x[0-9a-fA-F]+", window["address"]):
            raise RuntimeError("Rich clipboard window is not the scoped native client")
        command(["hyprctl", "dispatch", 'hl.dsp.focus({window="address:' + window["address"] + '"})'])
        wait_for(lambda: hypr("activewindow").get("address") == window["address"], "rich app focus")

    def rows():
        with sqlite3.connect(f"file:{home / '.local/share/orbit/orbit.sqlite3'}?mode=ro", uri=True, timeout=2) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM clips ORDER BY stamp DESC")]

    def payload_row(kind):
        for row in rows():
            meta = json.loads(row.get("meta") or "{}")
            if kind == "files" and row["kind"] == "files" and meta.get("paths") == paths: return row
            if kind == "html" and row["kind"] == "text" and row["text"] == plain: return row
            if kind == "image" and row["kind"] == "image" and meta.get("width") == 1024 and meta.get("height") == 512: return row
        return None

    def receive():
        target = run_dir / "rich-receiver.json"
        target.unlink(missing_ok=True)
        focus(receiver.pid, receiver_title)
        key("-M", "ctrl", "-k", "r", "-m", "ctrl")
        wait_for(target.is_file, "receiver reads native rich offer")
        return json.loads(target.read_text())

    def assert_payload(kind, packet, restored):
        if kind == "image":
            assert "image/png" in packet["formats"], packet
            assert packet.get("image") == dict(width=1024, height=512, rgb=[49, 87, 135]), packet
        elif kind == "files":
            assert packet["paths"] == paths and "text/uri-list" in packet["formats"], packet
            assert packet["gnome"].startswith("copy\n" if restored else "cut\n"), packet
            if restored: assert packet["kde"] == "0", packet
        else:
            assert packet["text"] == plain and "text/html" in packet["formats"], packet
            assert "<strong>" + token + "</strong>" in packet["html"], packet

    try:
        if not binary.is_file() or not all((tessdata / (lang + ".traineddata")).is_file() for lang in ("spa", "eng")):
            raise RuntimeError("Real OCR dependency missing: extracted Tesseract plus spa+eng tessdata in " + str(root))
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper_changed = True
        wrapper.write_text("#!/usr/bin/python3\nimport os,sys\n"
                           + "os.environ['TESSDATA_PREFIX']=" + repr(str(tessdata)) + "\n"
                           + "os.environ['LD_LIBRARY_PATH']=" + repr(str(root / "usr/lib/x86_64-linux-gnu")) + "+':' + os.environ.get('LD_LIBRARY_PATH','')\n"
                           + "os.execv(" + repr(str(binary)) + ", [" + repr(str(binary)) + ", *sys.argv[1:]])\n")
        wrapper.chmod(0o700)
        source_title = "Wysun clipboard source " + token
        receiver_title = "Wysun clipboard receiver " + token
        def start(role):
            log = (run_dir / ("rich-" + role + ".log")).open("w"); logs.append(log)
            process = subprocess.Popen(["/usr/bin/python3", str(Path(__file__).resolve()), "--role", role, "--token", token],
                                       env=env, cwd="/", stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            processes.append(process); return process
        source = start("source"); receiver = start("receiver")
        for kind, number in (("files", "2"), ("html", "3"), ("image", "1")):
            # Always reacquire the current surface/address after a hide/show.
            focus(source.pid, source_title)
            key("-M", "alt", "-k", number, "-m", "alt")
            row = wait_for(lambda: payload_row(kind), "installed history persists " + kind, timeout=20)
            packet = receive(); assert_payload(kind, packet, restored=False)
            if kind != "image":
                envelope = json.loads(row["blob"])
                assert envelope["version"] == 1 and envelope["formats"], "Rich MIME was not persisted"
            else:
                assert len(row["blob"]) > 256 * 1024 and row["thumb"], "Large PNG/thumbnail not persisted"
                def recognized():
                    current = next(item for item in rows() if item["id"] == row["id"])
                    meta = json.loads(current.get("meta") or "{}")
                    if meta.get("ocr_status") == "no disponible": raise RuntimeError("Real OCR unavailable: " + meta.get("ocr_error", ""))
                    return current if current["ocr_done"] and "WYSUN42" in current["ocr"].upper().replace(" ", "") else None
                row = wait_for(recognized, "real Tesseract OCR persisted WYSUN42", timeout=45)
            # Replace the live source offer, then restore through the PUBLIC UI.
            focus(source.pid, source_title)
            key("-M", "alt", "-k", "0", "-m", "alt")
            command([public, "clipboard"])
            wait_for(lambda: mapped(launcher_pid, "Wysun"), "installed clipboard UI maps")
            active = hypr("activewindow")
            if active.get("pid") != launcher_pid: raise RuntimeError("Installed clipboard UI failed to take focus")
            # URI paths also contain token; the HTML case must select its full
            # plain-text companion rather than the recently used file entry.
            query = "WYSUN42" if kind == "image" else (plain if kind == "html" else token)
            key(query, "-s", "350", "-k", "Return")
            wait_for(lambda: not mapped(launcher_pid, "Wysun"), "history keyboard restore closes launcher")
            packet = receive(); assert_payload(kind, packet, restored=True)
            persisted = next(item for item in rows() if item["id"] == row["id"])
            assert persisted["blob"] == row["blob"], "History payload unexpectedly changed"
            report["phases"].append(dict(kind=kind, direct_qt_roundtrip=True, installed_history_restore=True,
                                         persisted=True, ocr_real=(kind == "image"), stale_cut_normalized=(kind == "files")))
            result_path.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report["phases"][-1]), flush=True)
        report["result"] = "WYSUN_RICH_CLIPBOARD_NATIVE_OK"
        return report
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        for request in ("clients", "activewindow"):
            try: report[request] = hypr(request)
            except Exception as diagnostic: report[request] = dict(diagnostic_error=str(diagnostic))
        report["child_diagnostics"] = {role: (run_dir / ("rich-" + role + ".log")).read_text()[-4000:]
                                       for role in ("source", "receiver") if (run_dir / ("rich-" + role + ".log")).is_file()}
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=2)
        for log in logs: log.close()
        if wrapper_changed:
            if original is None: wrapper.unlink(missing_ok=True)
            else: wrapper.write_bytes(original); wrapper.chmod(original_mode)
        result_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("source", "receiver"), required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"rich-[0-9a-f]{10}", args.token): parser.error("Expected the private probe token")
    qt_role(args.role, args.token)
