#!/usr/bin/env python3
"""One-shot desktop keys. Dunst remains the sole notification engine.

--dry-run performs only state queries; --fixture JSON is allowed only with it.
No daemon, polling, shell commands, privilege escalation or media fallback after
an action fails. Public wrapper/shortcuts are owned by the session integrator.
"""
import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ACTIONS = ("volume-up", "volume-down", "volume-mute", "brightness-up",
           "brightness-down", "media-next", "media-previous", "media-play-pause", "media-stop")
SINK = "@DEFAULT_AUDIO_SINK@"


class ControlError(RuntimeError):
    pass


def host_environment(environ):
    env = dict(environ)
    appdir = env.get("APPDIR")
    if appdir:
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", os.defpath).split(os.pathsep)
                                    if p != appdir and not p.startswith(appdir + "/"))
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD", "APPIMAGE", "APPDIR", "ARGV0"):
        env.pop(key, None)
    env["LC_ALL"] = "C"
    return env


class Controller:
    def __init__(self, runner=None, available=None, environ=None):
        self.env = host_environment(os.environ if environ is None else environ)
        self.runner = runner or self._command
        self.available = available or (lambda name: shutil.which(name, path=self.env.get("PATH")))

    def _command(self, argv):
        try:
            result = subprocess.run(argv, env=self.env, text=True, capture_output=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ControlError("No se pudo ejecutar " + argv[0]) from error
        if result.returncode:
            # Do not log player metadata, server diagnostics or inherited data.
            raise ControlError(argv[0] + " terminó con código " + str(result.returncode))
        return result.stdout.strip()

    def _volume(self, backend):
        if backend == "wpctl":
            text = self.runner(["wpctl", "get-volume", SINK])
            match = re.fullmatch(r"Volume:\s*([0-9]+(?:\.[0-9]+)?)(\s+\[MUTED\])?", text.strip())
            if not match or not math.isfinite(float(match[1])):
                raise ControlError("Respuesta de volumen wpctl inválida")
            return dict(percent=round(float(match[1]) * 100), muted=bool(match[2]))
        text = self.runner(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        match = re.search(r"\b([0-9]+)%", text)
        mute = self.runner(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]).strip()
        if not match or mute not in ("Mute: yes", "Mute: no"):
            raise ControlError("Respuesta de volumen pactl inválida")
        return dict(percent=int(match[1]), muted=mute == "Mute: yes")

    def _brightness(self, device=None):
        argv = ["brightnessctl", "-m", "-c", "backlight"]
        if device:
            argv.extend(["-d", device])
        rows = list(csv.reader(self.runner(argv + ["info"]).strip().splitlines()))
        if len(rows) != 1 or len(rows[0]) != 5:
            raise ControlError("Se requiere un dispositivo backlight inequívoco")
        name, kind, current, _percent, maximum = rows[0]
        if kind != "backlight" or name.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_:.+-]+", name) or (device and name != device):
            raise ControlError("Dispositivo de brillo inesperado")
        try:
            current, maximum = int(current), int(maximum)
        except ValueError as error:
            raise ControlError("Valores de brillo inválidos") from error
        if not 0 <= current <= maximum <= 2**31 - 1 or maximum == 0:
            raise ControlError("Rango de brillo inválido")
        return dict(device=name, current=current, maximum=maximum, percent=round(100 * current / maximum))

    def _media(self, action):
        if self.available("mpc"):
            try:
                # Empty song format avoids reading track names into a report.
                status = self.runner(["mpc", "--format", "", "status"])
            except ControlError:
                status = ""
            if re.search(r"\[(?:playing|paused)\]", status):
                verb = {"play-pause": "toggle", "previous": "prev"}.get(action, action)
                return dict(backend="mpc", player="mpd", commands=[["mpc", verb]])
        if not self.available("playerctl"):
            raise ControlError("No hay reproductor MPD activo ni playerctl disponible")
        try:
            names = self.runner(["playerctl", "--list-all"]).splitlines()
        except ControlError as error:
            raise ControlError("No hay reproductores MPRIS disponibles") from error
        candidates = []
        for index, name in enumerate(dict.fromkeys(names)):
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name.startswith("-"):
                continue
            try:
                status = self.runner(["playerctl", "--player", name, "status"]).strip()
            except ControlError:
                continue
            if status in ("Playing", "Paused", "Stopped"):
                candidates.append(({"Playing": 0, "Paused": 1, "Stopped": 2}[status], index, name))
        if not candidates:
            raise ControlError("No hay reproductor MPRIS controlable")
        name = min(candidates)[2]
        return dict(backend="playerctl", player=name, commands=[["playerctl", "--player", name, action]])

    def plan(self, action):
        if action not in ACTIONS:
            raise ControlError("Acción desconocida")
        if action.startswith("media-"):
            return dict(action=action, **self._media(action.removeprefix("media-")))
        if action.startswith("volume-"):
            backend = "wpctl" if self.available("wpctl") else "pactl"
            if not self.available(backend):
                raise ControlError("No están disponibles wpctl ni pactl")
            state = self._volume(backend)
            if action == "volume-mute":
                commands = [[backend, "set-mute" if backend == "wpctl" else "set-sink-mute",
                             SINK if backend == "wpctl" else "@DEFAULT_SINK@", "toggle"]]
            else:
                target = max(0, min(100, state["percent"] + (5 if action == "volume-up" else -5)))
                if backend == "wpctl":
                    commands = [["wpctl", "set-volume", "-l", "1", SINK, f"{target / 100:.2f}"],
                                ["wpctl", "set-mute", SINK, "0"]]
                else:
                    commands = [["pactl", "set-sink-volume", "@DEFAULT_SINK@", str(target) + "%"],
                                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"]]
            return dict(action=action, backend=backend, before=state, commands=commands)
        if not self.available("brightnessctl"):
            raise ControlError("brightnessctl no está disponible")
        state = self._brightness()
        step = max(1, math.ceil(state["maximum"] * .05))
        floor = max(1, math.ceil(state["maximum"] * .05))
        target = min(state["maximum"], max(floor, state["current"] + (step if action == "brightness-up" else -step)))
        return dict(action=action, backend="brightnessctl", before=state, minimum_percent=5,
                    commands=[["brightnessctl", "-c", "backlight", "-d", state["device"], "set", str(target)]])

    def _osd(self, channel, state):
        binary = "dunstify" if self.available("dunstify") else "notify-send"
        if not self.available(binary):
            raise ControlError("No está disponible un cliente de notificaciones")
        percent = max(0, min(100, state["percent"]))
        if channel == "volume":
            muted = state["muted"]
            icon = "audio-volume-muted-symbolic" if muted or percent == 0 else (
                "audio-volume-low-symbolic" if percent <= 30 else
                "audio-volume-medium-symbolic" if percent <= 60 else "audio-volume-high-symbolic")
            summary = "Silenciado" if muted else "Volumen: " + str(percent) + "%"
            if muted:
                percent = 0
        else:
            icon, summary = "display-brightness-symbolic", "Brillo: " + str(percent) + "%"
        self.runner([binary, "-a", "Wysun", "-u", "low", "-t", "1500", "-i", icon,
                     "-h", "int:value:" + str(percent),
                     "-h", "string:x-dunst-stack-tag:wysun-" + channel, summary])

    def perform(self, action, dry_run=False):
        plan = self.plan(action)
        if dry_run:
            return dict(result="DRY_RUN", plan=plan, applied=False, notification_sent=False)
        # No retry/fallback to a different device/player after a mutation fails.
        for argv in plan["commands"]:
            self.runner(argv)
        result = dict(result="APPLIED", action=action, backend=plan["backend"], applied=True)
        if action.startswith("media-"):
            return dict(result, player=plan["player"], notification_sent=False)
        try:
            if action.startswith("volume-"):
                state, channel = self._volume(plan["backend"]), "volume"
            else:
                state, channel = self._brightness(plan["before"]["device"]), "brightness"
            self._osd(channel, state)
            result.update(state=state, notification_sent=True)
        except ControlError as error:
            # The device action already happened; report that separately from
            # feedback failure instead of executing it again on another backend.
            result.update(result="APPLIED_OSD_FAILED", notification_sent=False, error=str(error))
        return result


def fixture_controller(path):
    data = json.loads(Path(path).read_text())
    available = set(data["available"])
    responses = {tuple(row["argv"]): row for row in data["responses"]}
    def query(argv):
        row = responses.get(tuple(argv))
        if row is None or row.get("returncode", 0):
            raise ControlError("La fixture no permite esta consulta")
        return row.get("stdout", "")
    return Controller(query, lambda name: name in available, environ={})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fixture", type=Path, help="Read-only response fixture; requires --dry-run")
    args = parser.parse_args(argv)
    if args.fixture and not args.dry_run:
        parser.error("--fixture requiere --dry-run; nunca controla dispositivos")
    try:
        controller = fixture_controller(args.fixture) if args.fixture else Controller()
        result = controller.perform(args.action, dry_run=args.dry_run)
        result["fixture"] = bool(args.fixture)
        print(json.dumps(result, ensure_ascii=False))
        return int(result["result"] == "APPLIED_OSD_FAILED")
    except (ControlError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(result="FAILED", error=str(error)), ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
