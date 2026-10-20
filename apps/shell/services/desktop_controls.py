#!/usr/bin/env python3
"""Bounded, one-shot Wysun providers. No daemon, notification server or toast.

Presentation contracts adapted from caelestia-dots/shell services
Audio.qml, Brightness.qml, Nmcli.qml, NotifData.qml and Notifs.qml.
Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
See LICENSES/GPL-3.0.txt and THIRD_PARTY.md. Upstream has no per-file notices.
"""
import argparse
import contextlib
import fcntl
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

SHELL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wysun_key_controls", SHELL / "controls.py")
keys = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keys)
Error = keys.ControlError
DOMAINS = ("audio", "brightness", "network", "bluetooth", "battery", "notifications", "session")


def plain(value, limit=4096):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value)))[:limit]


def history(text):
    """Dunst typed values -> inert presentation. Never invent callable actions."""
    value = json.loads(text)
    groups = value.get("data")
    if not isinstance(groups, list) or any(not isinstance(g, list) for g in groups):
        raise Error("Historial de Dunst inválido")
    rows, seen = [], set()
    for group in groups:
        for item in group:
            if not isinstance(item, dict):
                continue
            def field(name, default=""):
                v = item.get(name, default)
                return v.get("data", default) if isinstance(v, dict) else v
            nid = str(field("id"))
            if not re.fullmatch(r"[0-9]{1,10}", nid) or int(nid) == 0 or int(nid) > 2**32-1 or nid in seen:
                continue
            seen.add(nid)
            rows.append(dict(id=nid, appName=plain(field("appname"), 128),
                             summary=plain(field("summary"), 512), body=plain(field("body")),
                             urgency=str(field("urgency", "normal")), actions=[]))
            if len(rows) >= 100:
                return rows
    return rows


def nmfields(line):
    """nmcli terse escaping (colons and backslashes), no shell interpolation."""
    fields, word, escaped = [], "", False
    for ch in line:
        if escaped:
            word += ch
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            fields.append(word)
            word = ""
        else:
            word += ch
    fields.append(word + ("\\" if escaped else ""))
    return fields


def percent(value, minimum=0):
    if not re.fullmatch(r"[0-9]{1,3}", str(value)) or not minimum <= int(value) <= 100:
        raise Error("Porcentaje inválido")
    return int(value)


class Providers:
    def __init__(self, runner=None, available=None, environ=None, power_root=None, fixture=False):
        self.env = keys.host_environment(os.environ if environ is None else environ)
        self.runner = runner or self.command
        self.available = available or (lambda name: shutil.which(name, path=self.env.get("PATH")))
        self.keys = keys.Controller(self.runner, self.available, self.env)
        self.power_root = Path(power_root or "/sys/class/power_supply")
        self.fixture = fixture

    def command(self, argv):
        try:
            p = subprocess.run(argv, env=self.env, capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired as exc:
            raise Error("El proveedor no respondió a tiempo") from exc
        except OSError as exc:
            raise Error("Proveedor no disponible: " + argv[0]) from exc
        if p.returncode:
            raise Error("El proveedor rechazó la operación: " + argv[0])
        return p.stdout.strip()

    def require(self, name):
        if not self.available(name):
            raise Error("No disponible: " + name)

    def audio(self):
        backend = "wpctl" if self.available("wpctl") else "pactl"
        self.require(backend)
        return dict(available=True, backend=backend, **self.keys._volume(backend))

    def brightness(self):
        self.require("brightnessctl")
        return dict(available=True, **self.keys._brightness())

    def network(self):
        self.require("nmcli")
        enabled = self.runner(["nmcli", "-t", "-f", "WIFI", "radio"])
        if enabled not in ("enabled", "disabled"):
            raise Error("Estado Wi-Fi inválido")
        devices = []
        for line in self.runner(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"]).splitlines():
            fields = nmfields(line)
            if len(fields) == 4:
                devices.append(dict(zip(("device", "type", "state", "connection"), fields)))
        saved = []
        for line in self.runner(["nmcli", "-t", "-f", "UUID,NAME,TYPE", "connection", "show"]).splitlines():
            fields = nmfields(line)
            if len(fields) == 3 and re.fullmatch(r"[0-9a-fA-F-]{36}", fields[0]):
                saved.append(dict(uuid=fields[0], name=fields[1], type=fields[2]))
        return dict(available=True, enabled=enabled == "enabled", devices=devices, saved=saved[:30])

    def bluetooth(self):
        self.require("bluetoothctl")
        text = self.runner(["bluetoothctl", "show"])
        powered = re.search(r"^\s*Powered: (yes|no)\s*$", text, re.M)
        if not powered:
            raise Error("No hay adaptador Bluetooth")
        devices = []
        # Paired devices only: never start discovery or request credentials.
        for line in self.runner(["bluetoothctl", "devices", "Paired"]).splitlines()[:20]:
            match = re.fullmatch(r"Device ([0-9A-Fa-f:]{17}) (.+)", line)
            if match:
                devices.append(dict(address=match[1], name=plain(match[2], 128)))
        return dict(available=True, enabled=powered[1] == "yes", devices=devices)

    def battery(self):
        for supply in sorted(self.power_root.glob("*")):
            def read(name):
                try:
                    return (supply / name).read_text().strip()
                except OSError:
                    return ""
            if read("type") != "Battery" or read("scope") == "Device":
                continue
            try:
                value = percent(read("capacity"))
            except Error:
                continue
            state = {"Charging": "Cargando", "Discharging": "En uso", "Full": "Carga completa",
                     "Not charging": "Conectada"}.get(read("status"), "Estado no disponible")
            return dict(available=True, percent=value, status=state)
        raise Error("No hay batería disponible")

    def notifications(self):
        self.require("dunstctl")
        level = self.runner(["dunstctl", "get-pause-level"])
        level = percent(level)
        return dict(available=True, pauseLevel=level, paused=level > 0,
                    items=history(self.runner(["dunstctl", "history"])))

    def session(self):
        self.require("gdbus")
        result = {}
        for name in ("Suspend", "Reboot", "PowerOff"):
            text = self.runner(["gdbus", "call", "--system", "--dest", "org.freedesktop.login1",
                                "--object-path", "/org/freedesktop/login1", "--method",
                                "org.freedesktop.login1.Manager.Can" + name])
            result[name.lower()] = text.strip() == "('yes',)"
        return dict(available=True, **result)

    def snapshot(self, domains):
        result = {}
        for domain in domains:
            if domain not in DOMAINS:
                raise Error("Proveedor desconocido")
            try:
                result[domain] = getattr(self, domain)()
            except (Error, ValueError, TypeError, KeyError, OSError) as exc:
                result[domain] = dict(available=False, error=str(exc) if isinstance(exc, Error) else "Respuesta del proveedor inválida")
        return result

    @contextlib.contextmanager
    def pause_guard(self):
        # Serialize with Recorder, without inspecting its project paths or data.
        if self.fixture:
            yield
            return
        state = Path(self.env.get("XDG_STATE_HOME") or Path(self.env.get("HOME", "~")) / ".local/state") / "loomrec"
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (state / "concentration.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Error("Wysun Recorder administra la concentración; intenta más tarde") from exc
            if (state / "concentration.json").exists():
                raise Error("Wysun Recorder administra la concentración; usa sus controles")
            yield

    def perform(self, action, value=""):
        """Validate from fresh state; one selected backend, no fallback after failure."""
        domain, _, verb = action.partition("-")
        if action == "notifications-pause":
            with self.pause_guard():
                before = self.notifications()
                self.runner(["dunstctl", "set-pause-level", "0" if before["paused"] else "100"])
        else:
            plans = {
                "audio-set": lambda s: [s["backend"], "set-volume" if s["backend"] == "wpctl" else "set-sink-volume",
                                         keys.SINK if s["backend"] == "wpctl" else "@DEFAULT_SINK@",
                                         str(percent(value)) + "%"],
                "audio-mute": lambda s: [s["backend"], "set-mute" if s["backend"] == "wpctl" else "set-sink-mute",
                                          keys.SINK if s["backend"] == "wpctl" else "@DEFAULT_SINK@", "toggle"],
                "brightness-set": lambda s: ["brightnessctl", "-c", "backlight", "-d", s["device"], "set", str(percent(value, 5)) + "%"],
                "network-toggle": lambda s: ["nmcli", "radio", "wifi", "off" if s["enabled"] else "on"],
                "network-connect": lambda s: self.saved_connection(s, value),
                "bluetooth-toggle": lambda s: ["bluetoothctl", "power", "off" if s["enabled"] else "on"],
                "bluetooth-connect": lambda s: self.paired_device(s, value, "connect"),
                "bluetooth-disconnect": lambda s: self.paired_device(s, value, "disconnect"),
                "notifications-remove": lambda s: self.remove_notice(s, value),
                "session-suspend": lambda s: self.session_command(s, "suspend"),
                "session-reboot": lambda s: self.session_command(s, "reboot"),
                "session-poweroff": lambda s: self.session_command(s, "poweroff"),
            }
            if action not in plans:
                raise Error("Acción desconocida")
            before = getattr(self, domain)()
            self.runner(plans[action](before))
        result = dict(ok=True, applied=not self.fixture, simulated=self.fixture, domain=domain)
        after = self.snapshot([domain])[domain]
        result["state"] = after
        if not after["available"]:
            result["warning"] = "Acción enviada; no se pudo comprobar el estado final"
        return result

    @staticmethod
    def saved_connection(state, value):
        if value not in {row["uuid"] for row in state["saved"]}:
            raise Error("La conexión ya no está disponible")
        return ["nmcli", "--wait", "2", "connection", "up", "uuid", value]

    @staticmethod
    def paired_device(state, value, verb):
        if value not in {row["address"] for row in state["devices"]}:
            raise Error("El dispositivo no está emparejado")
        return ["bluetoothctl", verb, value]

    @staticmethod
    def remove_notice(state, value):
        if value not in {row["id"] for row in state["items"]}:
            raise Error("El aviso ya no está en el historial")
        return ["dunstctl", "history-rm", value]

    def session_command(self, state, verb):
        if not state.get(verb):
            raise Error("La sesión no permite esta acción sin autorización adicional")
        self.require("systemctl")
        return ["systemctl", verb]


def fixture_provider(path):
    data = json.loads(Path(path).read_text())
    rows = {tuple(row["argv"]): row for row in data["responses"]}
    def query(argv):
        row = rows.get(tuple(argv))
        if row is None or row.get("returncode", 0):
            raise Error("Operación rechazada por la fixture")
        return row.get("stdout", "").strip()
    # No /sys, DBus, files in HOME, subprocesses or device actions in fixture mode.
    return Providers(query, lambda name: name in data["available"], environ={},
                     power_root=Path(path).parent / "fixture-power", fixture=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("snapshot", "action"))
    parser.add_argument("name")
    parser.add_argument("value", nargs="?", default="")
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args(argv)
    try:
        p = fixture_provider(args.fixture) if args.fixture else Providers()
        result = dict(ok=True, states=p.snapshot(args.name.split(","))) if args.operation == "snapshot" else p.perform(args.name, args.value)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (Error, OSError, ValueError, TypeError, KeyError):
        # No raw backend diagnostics or private metadata in logs/stderr.
        print(json.dumps(dict(ok=False, error="No se pudo completar la operación. Actualiza el panel y vuelve a intentar."), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
