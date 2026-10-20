"""Opt-in external-app cases for the integrator's already private portal runner.

run_cases(run_dir, env, command, start, wait_for, *, key=None, cases=..., obs_creation="rpc")
  command(argv, timeout=seconds) -> stdout text, raises on failure
  start(name, argv, extra_env=dict) -> Popen started with start_new_session=True
  key(*wtype_arguments) optionally uses the caller's persistent virtual seat.
  env["WYSUN_TEST_OBS_DBUS_DEBUG"]="1" opts in to G_DBUS_DEBUG=message
  only for the OBS child; its stdout stays in the caller's external-obs.log.

No standalone entry point, package installation, compositor, portal, or audio
service startup. Requires the caller's sole WYSUN-TEST-1, private bus/PipeWire,
fixture picker, network namespace with only loopback (UP), and no input/sound
devices. Every app uses a fresh private HOME/profile and exits before the next.
Availability, a mapped window, and API replies alone never produce PASS.
"""
import base64
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import threading
import time
import uuid


SOURCES = {
    "konsole": "https://docs.kde.org/stable_kf6/en/konsole/konsole/command-line-options.html",
    "firefox_protocol": "https://firefox-source-docs.mozilla.org/remote/marionette/Protocol.html",
    "firefox_ui": "https://github.com/mozilla/gecko-dev/blob/master/browser/actors/WebRTCParent.sys.mjs",
    "firefox_security": "https://firefox-source-docs.mozilla.org/remote/Security.html",
    "obs_launch": "https://obsproject.com/kb/launch-parameters",
    "obs_rpc": "https://github.com/obsproject/obs-websocket/blob/5.5.2/docs/generated/protocol.md",
    "obs_config": "https://github.com/obsproject/obs-websocket/blob/5.5.2/src/Config.cpp",
    "obs_recording": "https://github.com/obsproject/obs-studio/blob/30.2.3/UI/window-basic-main-outputs.cpp",
}


def _peer(path):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(str(path))
        pid, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != os.getuid():
        raise RuntimeError("Private socket belongs to another UID")
    return pid


def _guard(run_dir, env, command):
    run_dir = Path(run_dir).resolve()
    if run_dir.parent != Path("/tmp") or not run_dir.name.startswith("ws-"):
        raise RuntimeError("External cases require /tmp/ws-* from the nested runner")
    runtime = Path(env.get("XDG_RUNTIME_DIR", "/nonexistent")).resolve()
    if runtime != run_dir / "r":
        raise RuntimeError("Unexpected private runtime directory")
    for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        path = Path(env.get(name, "/nonexistent")).resolve()
        if path == run_dir or not path.is_relative_to(run_dir) or not path.is_dir():
            raise RuntimeError("Not a disposable directory: " + name)
    display = env.get("WAYLAND_DISPLAY", "")
    if not display or "/" in display:
        raise RuntimeError("Unexpected Wayland display")
    exe = Path(f"/proc/{_peer(runtime / display)}/exe").resolve()
    if exe.name != "Hyprland" or not exe.is_relative_to(Path("/tmp")):
        raise RuntimeError("Wayland peer is not the extracted test compositor")
    if env.get("DBUS_SESSION_BUS_ADDRESS", "").split(",", 1)[0] != "unix:path=" + str(runtime / "bus"):
        raise RuntimeError("Only the runner's private session bus is accepted")
    if Path(f"/proc/{_peer(runtime / 'bus')}/exe").resolve().name != "dbus-daemon":
        raise RuntimeError("Unexpected private bus peer")
    if env.get("DBUS_SYSTEM_BUS_ADDRESS") != "unix:path=" + str(run_dir / "no-system-bus"):
        raise RuntimeError("System bus must remain disabled")
    if Path(env.get("PIPEWIRE_RUNTIME_DIR", "/nonexistent")).resolve() != runtime or env.get("PIPEWIRE_REMOTE") != "pipewire-0":
        raise RuntimeError("Private PipeWire environment is required")
    pw_exe = Path(f"/proc/{_peer(runtime / 'pipewire-0')}/exe").resolve()
    if pw_exe.name != "pipewire":
        raise RuntimeError("Unexpected private PipeWire peer")
    if any(Path(path).exists() for path in ("/dev/input", "/dev/snd", "/dev/video0")) or list(Path("/dev/dri").glob("card*")):
        raise RuntimeError("Physical input, sound, camera, or DRM card devices are exposed")
    if {name for _, name in socket.if_nameindex()} != {"lo"}:
        raise RuntimeError("External cases require a network namespace with only loopback")
    monitors = json.loads(command(["hyprctl", "-j", "monitors"]))
    if len(monitors) != 1 or monitors[0].get("name") != "WYSUN-TEST-1":
        raise RuntimeError("Only WYSUN-TEST-1 may be shared")
    if not 0 < monitors[0]["width"] <= 4096 or not 0 < monitors[0]["height"] <= 4096:
        raise RuntimeError("Unexpected synthetic monitor dimensions")
    return run_dir, monitors[0]


def _private_path(path, parent):
    path = Path(path).resolve()
    if not path.is_relative_to(parent) or path == parent:
        raise RuntimeError("Output/profile escapes the disposable case directory")
    return path


def _descendant(pid, ancestor):
    for _ in range(40):
        if pid == ancestor:
            return True
        try:
            status = dict(line.split(":", 1) for line in Path(f"/proc/{pid}/status").read_text().splitlines() if ":" in line)
            if int(status["Uid"].split()[0]) != os.getuid():
                return False
            pid = int(status["PPid"])
        except (OSError, KeyError, ValueError):
            return False
        if pid <= 1:
            return False
    return False


def _stop(process):
    """Pin the live app/session members before stopping; do not leave workers."""
    if process.poll() is not None:
        for path in Path("/proc").iterdir():
            if path.name.isdigit():
                with contextlib.suppress(ProcessLookupError):
                    if os.getpgid(int(path.name)) == process.pid and os.getsid(int(path.name)) == process.pid:
                        raise RuntimeError("App exited leaving a session worker; abort this private runner before the next app")
        return
    if os.getpgid(process.pid) != process.pid or os.getsid(process.pid) != process.pid:
        raise RuntimeError("start() did not create a private app session; refusing group cleanup")
    descriptors = []
    try:
        for path in Path("/proc").iterdir():
            if not path.name.isdigit():
                continue
            pid = int(path.name)
            try:
                in_session = os.getpgid(pid) == process.pid and os.getsid(pid) == process.pid
                if not in_session and not _descendant(pid, process.pid):
                    continue
                status = dict(line.split(":", 1) for line in (path / "status").read_text().splitlines() if ":" in line)
                if int(status["Uid"].split()[0]) != os.getuid():
                    raise RuntimeError("Unexpected UID in owned app session")
                descriptor = os.pidfd_open(pid)
                in_session = os.getpgid(pid) == process.pid and os.getsid(pid) == process.pid
                if not in_session and not _descendant(pid, process.pid):
                    os.close(descriptor)
                    raise RuntimeError("App session changed while pinning cleanup")
                descriptors.append(descriptor)
            except (FileNotFoundError, ProcessLookupError):
                continue
        for descriptor in descriptors:
            with contextlib.suppress(ProcessLookupError):
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        def reap(deadline):
            pending = list(descriptors)
            while pending and time.monotonic() < deadline:
                poller = select.poll()
                for descriptor in pending:
                    poller.register(descriptor, select.POLLIN)
                ready = {descriptor for descriptor, _ in poller.poll(100)}
                pending = [descriptor for descriptor in pending if descriptor not in ready]
            return pending
        pending = reap(time.monotonic() + 4)
        for descriptor in pending:
            with contextlib.suppress(ProcessLookupError):
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
        if reap(time.monotonic() + 3):
            raise RuntimeError("Owned app workers did not exit; refusing the next external app")
        process.wait(timeout=3)
        for path in Path("/proc").iterdir():
            if path.name.isdigit():
                with contextlib.suppress(ProcessLookupError, FileNotFoundError):
                    if os.getpgid(int(path.name)) == process.pid and os.getsid(int(path.name)) == process.pid:
                        stat = (path / "stat").read_text()
                        if stat[stat.rfind(")") + 2:].split()[0] != "Z":
                            raise RuntimeError("New app worker survived teardown; abort private runner before continuing")
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def _free_port():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


def _read_exact(connection, count):
    data = bytearray()
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise RuntimeError("Local automation endpoint disconnected")
        data.extend(chunk)
    return bytes(data)


class _Marionette:
    """Minimal bounded official Marionette v3 client, only on private loopback."""
    def __init__(self, port):
        self.connection = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.connection.settimeout(10)
        self.sequence = 0
        try:
            hello = self.receive()
            if hello.get("applicationType") != "gecko" or hello.get("marionetteProtocol") != 3:
                raise RuntimeError("Not a Marionette v3 endpoint")
        except Exception:
            self.close()
            raise

    def close(self):
        self.connection.close()

    def receive(self):
        length = bytearray()
        while True:
            char = _read_exact(self.connection, 1)
            if char == b":":
                break
            if not char.isdigit() or len(length) >= 8:
                raise RuntimeError("Invalid Marionette length prefix")
            length.extend(char)
        size = int(length)
        if not 0 < size <= 2 * 1024 * 1024:
            raise RuntimeError("Oversized Marionette response")
        return json.loads(_read_exact(self.connection, size))

    def call(self, name, params=None):
        self.sequence += 1
        body = json.dumps([0, self.sequence, name, params or {}]).encode()
        self.connection.sendall(str(len(body)).encode() + b":" + body)
        response = self.receive()
        if not isinstance(response, list) or len(response) != 4 or response[:2] != [1, self.sequence]:
            raise RuntimeError("Unexpected Marionette response sequence")
        if response[2]:
            raise RuntimeError("Firefox " + name + ": " + str(response[2]))
        value = response[3]
        return value.get("value") if isinstance(value, dict) and "value" in value else value

    def script(self, source):
        return self.call("WebDriver:ExecuteScript", {"script": source, "args": [], "newSandbox": False})


class _ObsSocket:
    """Bounded RFC6455 text frames and obs-websocket 5.x RPC; no pip package."""
    def __init__(self, port, password):
        self.connection = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.connection.settimeout(10)
        self.sequence = 0
        try:
            self.identify(port, password)
        except Exception:
            self.close()
            raise

    def identify(self, port, password):
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.connection.sendall(request.encode())
        response = bytearray()
        while not response.endswith(b"\r\n\r\n"):
            response.extend(_read_exact(self.connection, 1))
            if len(response) > 8192:
                raise RuntimeError("Oversized WebSocket upgrade")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        headers = response.decode().split("\r\n")
        header_map = {h.split(":", 1)[0].lower(): h.split(":", 1)[1].strip() for h in headers[1:] if ":" in h}
        if " 101 " not in headers[0] or header_map.get("sec-websocket-accept") != expected:
            raise RuntimeError("Invalid OBS WebSocket upgrade")
        hello = self.receive()
        if hello.get("op") != 0:
            raise RuntimeError("OBS WebSocket did not send Hello")
        identify = dict(rpcVersion=1, eventSubscriptions=0)
        auth = hello["d"].get("authentication")
        if auth:
            secret = base64.b64encode(hashlib.sha256((password + auth["salt"]).encode()).digest()).decode()
            identify["authentication"] = base64.b64encode(hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
        self.send(dict(op=1, d=identify))
        if self.receive().get("op") != 2:
            raise RuntimeError("OBS WebSocket identification failed")

    def close(self):
        self.connection.close()

    def send(self, value, opcode=1):
        data = json.dumps(value).encode() if opcode == 1 else value
        mask = os.urandom(4)
        size = len(data)
        header = bytes([0x80 | opcode, 0x80 | size]) if size < 126 else bytes([0x80 | opcode, 0x80 | 126]) + struct.pack("!H", size)
        self.connection.sendall(header + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(data)))

    def receive(self):
        while True:
            first, second = _read_exact(self.connection, 2)
            if not first & 0x80 or second & 0x80:
                raise RuntimeError("Fragmented/masked OBS server frame is unsupported")
            size = second & 0x7f
            if size == 126:
                size = struct.unpack("!H", _read_exact(self.connection, 2))[0]
            elif size == 127:
                size = struct.unpack("!Q", _read_exact(self.connection, 8))[0]
            if size > 2 * 1024 * 1024:
                raise RuntimeError("Oversized OBS server frame")
            data = _read_exact(self.connection, size)
            opcode = first & 15
            if opcode == 9:
                self.send(data, opcode=10)
                continue
            if opcode != 1:
                raise RuntimeError("OBS WebSocket closed or sent an unsupported frame")
            return json.loads(data)

    def call(self, kind, **data):
        self.sequence += 1
        request_id = str(self.sequence)
        self.send(dict(op=6, d=dict(requestType=kind, requestId=request_id, requestData=data)))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            reply = self.receive()
            if reply.get("op") == 5:
                continue
            if reply.get("op") != 7 or reply["d"].get("requestId") != request_id:
                raise RuntimeError("Unexpected OBS RPC response")
            if not reply["d"]["requestStatus"]["result"]:
                raise RuntimeError("OBS " + kind + ": " + str(reply["d"]["requestStatus"]))
            return reply["d"].get("responseData", {})
        raise RuntimeError("OBS RPC response deadline")


@contextlib.contextmanager
def _fullscreen_fixture(fixture, run_dir, env, command, clients, wait_for, focus):
    """Cover only the owned RGB output, then restore the original fixture mode."""
    _, monitor = _guard(run_dir, env, command)
    if monitor.get("scale", 1) != 1 or monitor.get("transform", 0) != 0:
        raise RuntimeError("RGB fixture requires the unscaled synthetic output")
    pid, address = fixture["pid"], fixture["address"]
    def identity():
        proc = Path(f"/proc/{pid}")
        if proc.stat().st_uid != os.getuid():
            raise RuntimeError("Synthetic fixture PID changed owner")
        argv = (proc / "cmdline").read_bytes().split(b"\0")
        if str(run_dir / "opaque-window.py").encode() not in argv:
            raise RuntimeError("Synthetic fixture executable arguments changed")
        stat = (proc / "stat").read_text()
        return stat[stat.rfind(")") + 2:].split()[19]
    stamp = identity()
    def checked():
        if identity() != stamp:
            raise RuntimeError("Synthetic fixture PID was reused")
        return next((w for w in clients() if w.get("pid") == pid and w.get("address") == address
                     and w.get("title") == "Wysun synthetic opaque fixture" and w.get("mapped")
                     and not w.get("xwayland", True) and not w.get("hidden", False)
                     and w.get("monitor") == monitor["id"]), None)
    original = checked()
    if original is None or original.get("fullscreen") not in (0, 2):
        raise RuntimeError("Expected the owned fixture in normal or fullscreen mode")
    previous = original["fullscreen"]
    evidence = dict(pid=pid, address=address, previous_mode=previous, output=monitor["name"], restored=False)
    changed = False
    try:
        focus(original)
        if previous == 0:
            changed = True
            command(["hyprctl", "dispatch", 'hl.dsp.window.fullscreen({mode="fullscreen",action="set"})'])
        def covers_output():
            window = checked()
            return window if window and window.get("fullscreen") == 2 and window.get("size") == [monitor["width"], monitor["height"]] \
                and window.get("at") == [monitor.get("x", 0), monitor.get("y", 0)] else None
        evidence["covered_window"] = wait_for(covers_output, "owned RGB fixture covers the synthetic output")
        yield evidence
    finally:
        if changed:
            _guard(run_dir, env, command)
            window = checked()
            if window is None:
                raise RuntimeError("Owned RGB fixture disappeared before fullscreen restoration")
            focus(window)
            command(["hyprctl", "dispatch", 'hl.dsp.window.fullscreen({mode="fullscreen",action="unset"})'])
            def restored():
                window = checked()
                return window if window and window.get("fullscreen") == previous else None
            wait_for(restored, "owned RGB fixture fullscreen mode restored")
        evidence["restored"] = True


_PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Wysun external browser TOKEN</title>
<style>html,body{height:100%;margin:0;background:#315787;color:white;font:20px sans-serif}
button{margin:20px;padding:20px}video{position:absolute;right:16px;bottom:16px;width:240px;height:150px}</style>
<button id="share" autofocus>Share only the synthetic desktop</button><p id="state">Ready</p><video muted playsinline></video>
<script>
let started=false;
document.querySelector('#share').onclick=async event=>{
 if(started)return;started=true;
 let stream;let stage='gesture';
 const report={trusted:event.isTrusted,activation:navigator.userActivation.isActive,secure:isSecureContext};
 try{
  if(!report.trusted||!report.activation||!report.secure)throw Error('No trusted transient user activation');
  stage='getDisplayMedia';document.querySelector('#state').textContent='Requesting synthetic screen';
  stream=await navigator.mediaDevices.getDisplayMedia({video:{frameRate:{max:8}},audio:false});
  const tracks=stream.getVideoTracks();if(tracks.length!==1||stream.getAudioTracks().length)throw Error('Unexpected tracks');
  const video=document.querySelector('video');video.srcObject=stream;await video.play();stage='decode';
  const canvas=document.createElement('canvas');canvas.width=64;canvas.height=40;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  const deadline=performance.now()+12000;const observations=[];let decoded=false;
  Object.assign(report,{width:video.videoWidth,height:video.videoHeight,presentedFrames:0,
    matchingSyntheticPixels:0,nonblackPixels:0,pixelSamples:[],frameObservations:observations,
    settings:tracks[0].getSettings(),audioTracks:0,decodeBudgetMs:12000});
  while(performance.now()<deadline&&observations.length<128){
   const frame=await new Promise(resolve=>{
    const timer=setTimeout(()=>{video.cancelVideoFrameCallback(callback);resolve(null)},Math.max(1,deadline-performance.now()));
    const callback=video.requestVideoFrameCallback((now,meta)=>{clearTimeout(timer);resolve(meta)});
   });
   if(!frame)break;
   ctx.drawImage(video,0,0,64,40);
   const pixels=ctx.getImageData(0,0,64,40).data;let matches=0;let light=0;
   for(let i=0;i<pixels.length;i+=4){if(Math.abs(pixels[i]-49)<18&&Math.abs(pixels[i+1]-87)<18&&Math.abs(pixels[i+2]-135)<18)matches++;
    if(pixels[i]+pixels[i+1]+pixels[i+2]>40)light++;}
   const samples=[[0,0],[32,0],[63,0],[0,20],[32,20],[63,20],[0,39],[63,39]].map(([x,y])=>{
    const i=(y*64+x)*4;return {x,y,rgba:Array.from(pixels.slice(i,i+4))};
   });
   const measured={width:video.videoWidth,height:video.videoHeight,presentedFrames:frame.presentedFrames,
    mediaTime:frame.mediaTime,matchingSyntheticPixels:matches,nonblackPixels:light,pixelSamples:samples};
   observations.push({...measured,elapsedMs:Math.round(performance.now()-(deadline-12000))});
   Object.assign(report,measured);
   decoded=!!(video.videoWidth&&video.videoHeight&&frame.presentedFrames&&matches>=20&&light>=100);
   if(decoded)break;
  }
  report.observedFrames=observations.length;
  // The diagnostic is decoded getDisplayMedia video from the guarded private
  // output, never a CSS rendering or a replacement for the RGB assertion.
  if(observations.length){
   report.decodedPNG=canvas.toDataURL('image/png');
  }
  if(!decoded)throw Error('No synthetic RGB content in decoded screen frame within 12000ms');
  report.ok=true;
 }catch(error){Object.assign(report,{ok:false,stage,error:String(error)});}
 finally{if(stream)stream.getTracks().forEach(track=>track.stop());
  document.querySelector('#state').textContent=JSON.stringify(report);
  await fetch('result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(report)});}
};
</script></html>"""


@contextlib.contextmanager
def _page_server(token):
    result = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.client_address[0] != "127.0.0.1" or self.path != "/" + token + "/":
                self.send_error(404)
                return
            body = _PAGE.replace("TOKEN", token).encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
            self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if self.client_address[0] != "127.0.0.1" or self.path != "/" + token + "/result" or not 0 < size <= 262144:
                self.send_error(400)
                return
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                self.send_error(400)
                return
            result.update(value)
            self.send_response(204); self.end_headers()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port) + "/" + token + "/", result
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def run_cases(run_dir, env, command, start, wait_for, *, key=None, cases=("konsole", "firefox", "obs"), obs_audio="silent", obs_creation="rpc"):
    # "silent" is a compatibility recording with an encoded, measured silent
    # track. "none" requires a genuinely audio-free container, without fallback.
    run_dir, monitor = _guard(run_dir, env, command)
    if not cases or any(name not in ("konsole", "firefox", "obs") for name in cases) or len(set(cases)) != len(cases):
        raise ValueError("Choose distinct konsole/firefox/obs cases")
    if obs_audio not in ("none", "silent"):
        raise ValueError("obs_audio must be none (strict video-only) or silent (one verified silent track)")
    if obs_creation not in ("rpc", "collection"):
        raise ValueError("obs_creation must be rpc or collection; no automatic fallback")
    obs_dbus_debug = "obs" in cases and env.get("WYSUN_TEST_OBS_DBUS_DEBUG") == "1"
    root = run_dir / ("external-" + uuid.uuid4().hex[:10]); root.mkdir(mode=0o700)
    report = dict(result="INCOMPLETE", requested_cases=list(cases), obs_audio_policy=obs_audio,
                  obs_dbus_diagnostics=obs_dbus_debug, obs_creation_mode=obs_creation, cases={}, sources=SOURCES,
                  limits=["nested synthetic output only", "fixture picker, not human consent", "no physical-session claim"])
    result_path = run_dir / "native-external-apps-result.json"
    key = key or (lambda *args: command(["wtype", "-s", "200", *args]))
    current = None
    automation = None

    def clients():
        return json.loads(command(["hyprctl", "-j", "clients"]))

    def native(process, description, title_pattern=None):
        def mapped():
            matches = [w for w in clients() if w.get("mapped") and _descendant(w.get("pid", 0), process.pid)]
            if any(w.get("xwayland", True) for w in matches):
                raise RuntimeError(description + " opened through XWayland")
            return next((w for w in matches if w.get("acceptsInput", True) and not w.get("hidden", False)
                         and (title_pattern is None or re.fullmatch(title_pattern, w.get("title", "")))), None)
        window = wait_for(mapped, description + " native window", timeout=25)
        report["cases"][case]["native_window"] = window
        return window

    def focus(window):
        address = window["address"]
        if not re.fullmatch(r"0x[0-9a-fA-F]+", address):
            raise RuntimeError("Unexpected native window address")
        command(["hyprctl", "dispatch", 'hl.dsp.focus({window="address:' + address + '"})'])
        wait_for(lambda: json.loads(command(["hyprctl", "-j", "activewindow"])).get("address") == address, "external app native focus")

    def binary(name, preferred=None):
        found = preferred if preferred and Path(preferred).is_file() else shutil.which(name, path=env.get("PATH"))
        if not found:
            raise RuntimeError("Missing external test dependency: " + name + "; do not install host packages")
        return str(Path(found).resolve())

    def launch(name, argv, extra):
        nonlocal current
        # Do not inherit an AppImage, user Python import path, X11 display, or a
        # browser sandbox-disable override. --no-sandbox is never used.
        stripped = ["APPIMAGE", "APPDIR", "ARGV0", "DISPLAY", "PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH",
                    "G_DBUS_DEBUG", "MOZ_DISABLE_CONTENT_SANDBOX", "MOZ_DISABLE_GMP_SANDBOX", "MOZ_DISABLE_RDD_SANDBOX", "MOZ_DISABLE_GPU_SANDBOX"]
        # Opt-in applies after stripping inherited diagnostics and only to this
        # guarded OBS process, never the parent, portal, Firefox or Konsole.
        diagnostic = ["G_DBUS_DEBUG=message"] if name == "obs" and obs_dbus_debug else []
        current = start("external-" + name, ["/usr/bin/env", *sum((["-u", item] for item in stripped), []), *diagnostic, *argv], extra_env=extra)
        if current.poll() is not None:
            raise RuntimeError(name + " exited before native-window verification: " + str(current.returncode))
        if os.getpgid(current.pid) != current.pid or os.getsid(current.pid) != current.pid:
            raise RuntimeError("start() must create a new session for each external app")
        return current

    try:
        for case in cases:
            _guard(run_dir, env, command)
            folder = root / case; folder.mkdir(mode=0o700)
            extra = {}
            for variable, suffix in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state")):
                path = folder / suffix; path.mkdir(mode=0o700); extra[variable] = str(path)
            extra.update(QT_QPA_PLATFORM="wayland", GDK_BACKEND="wayland", MOZ_ENABLE_WAYLAND="1")
            started = time.monotonic()
            report["cases"][case] = dict(result="INCOMPLETE", folder=str(folder), cleanup=False)
            result_path.write_text(json.dumps(report, indent=2) + "\n")
            try:
                if case == "konsole":
                    token = "wysun-terminal-" + uuid.uuid4().hex[:10]
                    marker = folder / "terminal.json"
                    script = folder / "terminal.py"
                    script.write_text("import json,os,sys\nfrom pathlib import Path\n"
                        + "target=Path(" + repr(str(marker)) + ")\n"
                        + "token=" + repr(token) + "\n"
                        + "print('\\033]0;Wysun native terminal '+token+'\\007',flush=True)\n"
                        + "def publish(value):\n p=target.with_suffix('.tmp');p.write_text(json.dumps(value));p.replace(target)\n"
                        + "publish(dict(stage='ready',tty=os.isatty(0),pid=os.getpid()))\n"
                        + "line=sys.stdin.readline().rstrip('\\n')\n"
                        + "publish(dict(stage='exited',tty=os.isatty(0),input=line,token=token))\n"
                        + "sys.exit(0 if line==token else 17)\n")
                    process = launch(case, [binary("konsole"), "--separate", "--nofork", "--builtin-profile", "--workdir", extra["HOME"],
                        "-p", "LocalTabTitleFormat=%w", "-e", "/usr/bin/python3", script], extra)
                    window = native(process, "Konsole"); focus(window)
                    wait_for(marker.is_file, "Konsole command reached its pseudo-terminal")
                    if not json.loads(marker.read_text()).get("tty"):
                        raise RuntimeError("Konsole fixture is not attached to a terminal")
                    key(token, "-k", "Return")
                    wait_for(lambda: json.loads(marker.read_text()).get("stage") == "exited", "Konsole keyboard input and child exit marker")
                    data = json.loads(marker.read_text())
                    if data.get("input") != token or not data.get("tty"):
                        raise RuntimeError("Konsole did not deliver exact native terminal input")
                    wait_for(lambda: process.poll() is not None, "Konsole closes after its child exits")
                    if process.returncode != 0:
                        raise RuntimeError("Konsole exit status " + str(process.returncode))
                    result = dict(native=True, focus=True, terminal_input=True, child_marker=True, exit_code=0)

                elif case == "firefox":
                    port = _free_port()
                    profile = folder / "profile"; profile.mkdir(mode=0o700)
                    prefs = {"marionette.port": port, "browser.shell.checkDefaultBrowser": False,
                        "browser.startup.homepage_override.mstone": "ignore", "browser.aboutwelcome.enabled": False,
                        "datareporting.policy.dataSubmissionEnabled": False, "toolkit.telemetry.enabled": False,
                        "network.captive-portal-service.enabled": False, "network.connectivity-service.enabled": False,
                        "media.webrtc.capture.allow-pipewire": True}
                    (profile / "user.js").write_text("\n".join("user_pref(" + json.dumps(k) + "," + json.dumps(v) + ");" for k, v in prefs.items()) + "\n")
                    with _page_server(uuid.uuid4().hex) as (url, packet):
                        process = launch(case, [binary("firefox-esr", "/usr/lib/firefox-esr/firefox-esr"), "--no-remote", "--profile", profile,
                            "--marionette", "--remote-allow-system-access", "--new-window", url], extra)
                        window = native(process, "Firefox ESR"); focus(window)
                        def connect():
                            try: return _Marionette(port)
                            except (ConnectionRefusedError, socket.timeout): return None
                        automation = wait_for(connect, "Firefox private Marionette endpoint", timeout=25)
                        session = automation.call("WebDriver:NewSession", {"capabilities": {"alwaysMatch": {"acceptInsecureCerts": False}}})
                        automation.call("Marionette:SetContext", {"value": "content"})
                        automation.call("WebDriver:Navigate", {"url": url})
                        element = automation.call("WebDriver:FindElement", {"using": "css selector", "value": "#share"})
                        element_id = element.get("element-6066-11e4-a52e-4f735466cecf")
                        if not element_id:
                            raise RuntimeError("Firefox did not return a WebDriver element")
                        # This is WebDriver's trusted element-click input, not
                        # ExecuteScript calling getDisplayMedia without a gesture.
                        automation.call("WebDriver:ElementClick", {"id": element_id})
                        automation.call("Marionette:SetContext", {"value": "chrome"})
                        def allow_prompt():
                            observed = automation.script("""
const notification=document.getElementById('webRTC-shareDevices-notification');
const list=document.getElementById('webRTC-selectWindow-menulist');
if(!notification||!list||!window.PopupNotifications.panel.state.includes('open'))return {pending:true};
const choices=[...document.querySelectorAll('#webRTC-selectWindow-menupopup menuitem')].filter(x=>!x.disabled&&x.value!='-1');
if(choices.length!==1)throw Error('Expected exactly one PipeWire OS-picker option, got '+choices.length);
list.selectedItem=choices[0];choices[0].dispatchEvent(new Event('command',{bubbles:true}));
const button=notification.button||notification.querySelector('.popup-notification-primary-button');
if(notification.hasAttribute('invalidselection')||!button||button.disabled)return {pending:true,choices:choices.length,buttonFound:!!button};
button.click();return {permissionUI:true,choices:choices.length};
""")
                            (folder / "permission-ui.json").write_text(json.dumps(observed, indent=2) + "\n")
                            return observed if observed and observed.get("permissionUI") else None
                        permission = wait_for(allow_prompt, "Firefox native sharing permission UI", timeout=20)
                        data = wait_for(lambda: dict(packet) if packet else None, "Firefox decoded getDisplayMedia frame", timeout=35)
                        png_url = data.pop("decodedPNG", None)
                        if png_url is not None:
                            prefix = "data:image/png;base64,"
                            if not isinstance(png_url, str) or not png_url.startswith(prefix) or len(png_url) > 131072:
                                data["decodedPNGError"] = "Invalid bounded PNG data URL"
                            else:
                                try:
                                    png = base64.b64decode(png_url[len(prefix):], validate=True)
                                    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                                        raise ValueError("Invalid PNG signature")
                                    image_path = folder / "decoded-screen-frame.png"
                                    image_path.write_bytes(png)
                                    data["decodedPNGPath"] = str(image_path)
                                except ValueError as error:
                                    data["decodedPNGError"] = str(error)
                        (folder / "browser-frame.json").write_text(json.dumps(data, indent=2) + "\n")
                        if not data.get("ok") or not data.get("trusted") or not data.get("activation") or data.get("audioTracks") != 0:
                            raise RuntimeError("Firefox getDisplayMedia: " + str(data))
                        result = dict(native=True, focus=True, getDisplayMedia=True, trusted_gesture=True,
                            permission_ui=permission, decoded_frame=data, sandbox_disabled=False,
                            automation="Marionette chrome scope only for the real permission UI; private profile/loopback",
                            browser_version=session.get("capabilities", {}).get("browserVersion") if isinstance(session, dict) else None)

                else:
                    source_kind = "pipewire-screen-capture-source"
                    report["cases"][case]["creation_mode"] = obs_creation
                    port = _free_port(); password = uuid.uuid4().hex
                    recordings = folder / "recordings"; recordings.mkdir()
                    config = Path(extra["XDG_CONFIG_HOME"]) / "obs-studio"
                    profile = config / "basic/profiles/WysunSynthetic"; profile.mkdir(parents=True)
                    scenes = config / "basic/scenes"; scenes.mkdir(parents=True)
                    plugin = config / "plugin_config/obs-websocket"; plugin.mkdir(parents=True)
                    (plugin / "config.json").write_text(json.dumps(dict(first_load=False, server_enabled=True, server_port=port,
                        alerts_enabled=False, auth_required=True, server_password=password)))
                    # In OBS30.2.3 FirstRun=true means the initial wizard has
                    # already been offered. false + no LastVersion queues a
                    # modal auto-configuration dialog over the main window.
                    (config / "global.ini").write_text("[General]\nFirstRun=true\n[Basic]\nProfile=WysunSynthetic\nProfileDir=WysunSynthetic\nSceneCollection=WysunSynthetic\nSceneCollectionFile=WysunSynthetic\n")
                    # OBS's stock AV muxer/UI is not universally video-only.
                    # Choose the policy before launch; never silently retry and
                    # relabel an encoded silent track as an absent audio track.
                    tracks = "1" if obs_audio == "silent" else "0"
                    (profile / "basic.ini").write_text("[General]\nName=WysunSynthetic\n[Output]\nMode=Simple\nFilenameFormatting=Wysun-external-%CCYY-%MM-%DD-%hh-%mm-%ss\n"
                        + "[SimpleOutput]\nRecEncoder=x264\nRecQuality=Small\nRecFormat2=mkv\nRecTracks=" + tracks + "\nPreset=ultrafast\nFilePath=" + str(recordings) + "\n"
                        + "[Video]\nBaseCX=" + str(monitor["width"]) + "\nBaseCY=" + str(monitor["height"]) + "\nOutputCX=320\nOutputCY=200\nFPSType=0\nFPSCommon=12\n"
                        + "[Audio]\nSampleRate=48000\nChannelSetup=Stereo\nMonitoringDeviceId=disabled\n")
                    scene = dict(name="WysunSynthetic", id="scene", versioned_id="scene", settings=dict(items=[]), mixers=0)
                    sources = [scene]
                    if obs_creation == "collection":
                        # Loading the real source with the scene on OBS's UI
                        # startup avoids creating it on the RPC worker. This is
                        # an explicit case choice, never a fallback after RPC.
                        source_uuid = str(uuid.uuid4())
                        sources.insert(0, dict(name="WysunPrivatePipeWire", uuid=source_uuid, id=source_kind,
                            versioned_id=source_kind, settings=dict(ShowCursor=False), mixers=0, enabled=True))
                        scene["settings"].update(id_counter=1, items=[dict(name="WysunPrivatePipeWire",
                            source_uuid=source_uuid, id=1, visible=True, locked=False, rot=0.0,
                            pos=dict(x=0.0, y=0.0), scale=dict(x=1.0, y=1.0), align=5,
                            bounds_type=0, bounds_align=0, bounds=dict(x=0.0, y=0.0))])
                    (scenes / "WysunSynthetic.json").write_text(json.dumps(dict(name="WysunSynthetic", current_scene="WysunSynthetic",
                        current_program_scene="WysunSynthetic", scene_order=[dict(name="WysunSynthetic")],
                        sources=sources, groups=[], transitions=[], quick_transitions=[])))
                    process = launch(case, [binary("obs"), "--multi", "--profile", "WysunSynthetic", "--collection", "WysunSynthetic", "--disable-missing-files-check", "--websocket_ipv4_only"], extra)
                    # UpdateTitleBar includes both profile and collection.
                    # Do not select an initial dialog or a transient Qt window.
                    window = native(process, "OBS Studio", title_pattern=
                        r"OBS (?:Studio )?\d.* - [^:]+: WysunSynthetic - [^:]+: WysunSynthetic")
                    focus(window)
                    def connect():
                        try: return _ObsSocket(port, password)
                        except (ConnectionRefusedError, socket.timeout): return None
                    automation = wait_for(connect, "OBS private WebSocket v5 endpoint", timeout=25)
                    version = automation.call("GetVersion")
                    kinds = automation.call("GetInputKindList")["inputKinds"]
                    if source_kind not in kinds:
                        raise RuntimeError("OBS linux-pipewire input unavailable; loaded input kinds: " + str(kinds))
                    inputs = automation.call("GetInputList")["inputs"]
                    if obs_creation == "rpc" and inputs:
                        raise RuntimeError("Expected an empty synthetic OBS collection, got " + str(inputs))
                    if obs_creation == "collection" and (len(inputs) != 1 or inputs[0].get("inputName") != "WysunPrivatePipeWire"
                                                         or inputs[0].get("inputKind") != source_kind):
                        raise RuntimeError("Expected exactly the preloaded real PipeWire source, got " + str(inputs))
                    special = automation.call("GetSpecialInputs")
                    if any(special.values()):
                        raise RuntimeError("OBS created unexpected desktop/microphone inputs: " + str(special))
                    automation.call("SetVideoSettings", baseWidth=monitor["width"], baseHeight=monitor["height"], outputWidth=320, outputHeight=200, fpsNumerator=12, fpsDenominator=1)
                    if obs_creation == "rpc":
                        automation.call("CreateInput", sceneName="WysunSynthetic", inputName="WysunPrivatePipeWire", inputKind=source_kind,
                            inputSettings={"cursor_mode": 1}, sceneItemEnabled=True)
                    automation.call("SetCurrentProgramScene", sceneName="WysunSynthetic")
                    actual = automation.call("GetInputSettings", inputName="WysunPrivatePipeWire")
                    if actual.get("inputKind") != source_kind:
                        raise RuntimeError("OBS did not instantiate the real PipeWire source")
                    # The caller already owns this opaque fullscreen fixture.
                    # Match its exact script path as well as title, never a host window.
                    def opaque():
                        for item in clients():
                            if item.get("title") != "Wysun synthetic opaque fixture" or item.get("xwayland", True):
                                continue
                            try: argv = Path(f"/proc/{item['pid']}/cmdline").read_bytes().split(b"\0")
                            except OSError: continue
                            if str(run_dir / "opaque-window.py").encode() in argv:
                                return item
                        return None
                    fixture = wait_for(opaque, "guarded existing synthetic RGB fixture")
                    focus(fixture)
                    with _fullscreen_fixture(fixture, run_dir, env, command, clients, wait_for, focus) as fullscreen_evidence:
                        report["cases"][case]["fixture_fullscreen"] = fullscreen_evidence
                        item_id = automation.call("GetSceneItemId", sceneName="WysunSynthetic", sourceName="WysunPrivatePipeWire")["sceneItemId"]
                        wait_for(lambda: automation.call("GetSceneItemTransform", sceneName="WysunSynthetic", sceneItemId=item_id)["sceneItemTransform"].get("sourceWidth", 0) > 0,
                                 "OBS PipeWire source negotiated video", timeout=25)
                        automation.call("StartRecord")
                        wait_for(lambda: automation.call("GetRecordStatus").get("outputActive"), "OBS recording active")
                        time.sleep(2)
                        stopped = automation.call("StopRecord")
                        wait_for(lambda: not automation.call("GetRecordStatus").get("outputActive"), "OBS recording finalized")
                        output = _private_path(stopped["outputPath"], recordings)
                        wait_for(lambda: output.is_file() and output.stat().st_size > 1024, "OBS recording file")
                        probe = json.loads(command([binary("ffprobe"), "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", output]))
                        video = [item for item in probe["streams"] if item["codec_type"] == "video"]
                        audio = [item for item in probe["streams"] if item["codec_type"] == "audio"]
                        duration = float(probe.get("format", {}).get("duration", "0"))
                        if len(video) != 1 or int(video[0].get("nb_read_frames", 0)) < 6 or not 0.5 <= duration <= 10:
                            raise RuntimeError("OBS recording has no bounded decoded video stream: " + str(probe))
                        if len(audio) != (1 if obs_audio == "silent" else 0):
                            raise RuntimeError("OBS audio stream count differs from explicit " + obs_audio + " policy: " + str(probe))
                        audio_evidence = dict(policy=obs_audio, streams=len(audio), hardware_inputs=False)
                        if audio:
                            pcm = folder / "recorded-silence.s16le"
                            command([binary("ffmpeg"), "-v", "error", "-nostdin", "-y", "-i", output, "-map", "0:a:0",
                                "-t", "10", "-ac", "1", "-ar", "48000", "-f", "s16le", pcm])
                            raw = pcm.read_bytes()
                            if len(raw) < 48000 or len(raw) > 960000 or len(raw) % 2:
                                raise RuntimeError("OBS silent track did not decode to a bounded PCM stream")
                            samples = [value[0] for value in struct.iter_unpack("<h", raw)]
                            peak = max(map(abs, samples)); rms = math.sqrt(sum(value * value for value in samples) / len(samples))
                            if peak > 2 or rms > 1:
                                raise RuntimeError("OBS audio track is not synthetic silence: " + str(dict(peak=peak, rms=rms)))
                            audio_evidence.update(description="encoded silent track, NOT an audio-free file", pcm_samples=len(samples), peak_pcm16=peak, rms_pcm16=rms)
                        pixel = folder / "recorded-rgb.bin"
                        command([binary("ffmpeg"), "-v", "error", "-nostdin", "-y", "-ss", "0.5", "-i", output, "-map", "0:v:0", "-frames:v", "1", "-vf", "scale=1:1:flags=area", "-pix_fmt", "rgb24", "-f", "rawvideo", pixel])
                        rgb = list(pixel.read_bytes())
                        if len(rgb) != 3 or any(abs(a - b) > 15 for a, b in zip(rgb, (49, 87, 135))):
                            raise RuntimeError("Decoded OBS recording does not contain the synthetic RGB output: " + str(rgb))
                        result = dict(native=True, focus=True, pipewire_input=source_kind, creation_mode=obs_creation, recording=str(output),
                            decoded_frames=int(video[0]["nb_read_frames"]), rgb=rgb, audio=audio_evidence, version=version,
                            picker="caller fixture selecting WYSUN-TEST-1, not human consent")

                report["cases"][case].update(result="PASS", elapsed_ms=round((time.monotonic() - started) * 1000, 1), evidence=result)
            except Exception as error:
                report["cases"][case]["error"] = type(error).__name__ + ": " + str(error)
                # Preserve live dialog/title/address evidence before finally
                # stops the owned app; outer diagnostics happen after cleanup.
                for kind in ("clients", "activewindow"):
                    with contextlib.suppress(Exception):
                        report["cases"][case]["failure_" + kind] = json.loads(command(["hyprctl", "-j", kind]))
                if current:
                    report["cases"][case]["failure_returncode"] = current.poll()
                raise
            finally:
                if automation:
                    if isinstance(automation, _ObsSocket):
                        with contextlib.suppress(Exception):
                            if automation.call("GetRecordStatus").get("outputActive"):
                                automation.call("StopRecord")
                    automation.close(); automation = None
                if current:
                    _stop(current); current = None
                report["cases"][case]["cleanup"] = True
                result_path.write_text(json.dumps(report, indent=2) + "\n")
        report["result"] = "WYSUN_NATIVE_EXTERNAL_APPS_OK" if set(cases) == {"konsole", "firefox", "obs"} else "WYSUN_NATIVE_EXTERNAL_CASES_OK"
        return report
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        for kind in ("clients", "activewindow"):
            with contextlib.suppress(Exception):
                report[kind] = json.loads(command(["hyprctl", "-j", kind]))
        raise
    finally:
        result_path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit("Import run_cases only inside the integrator's guarded private portal runner; no standalone launch.")
