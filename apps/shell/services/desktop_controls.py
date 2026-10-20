#!/usr/bin/env python3
"""Bounded, one-shot providers for Wysun quick settings and session.

Dunst remains the only notification server: this file only reads and edits its
history with ``dunstctl`` and never starts a notification server or a toast.
Audio and brightness are observed directly by QML (PipeWire and sysfs); they are
not duplicated here.

Presentation contracts adapted from caelestia-dots/shell services
Audio.qml, Brightness.qml, Nmcli.qml, NotifData.qml and Notifs.qml.
Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Source commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
See LICENSES/GPL-3.0.txt and THIRD_PARTY.md. Upstream has no per-file notices.
"""
import argparse
import html
import importlib.util
import json
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
DOMAINS = ("network", "bluetooth", "battery", "notifications", "session")
# Every action is validated against a fresh snapshot before it runs.
ACTIONS = ("network-toggle", "network-connect",
           "bluetooth-toggle", "bluetooth-connect", "bluetooth-disconnect",
           "notifications-pause", "notifications-remove", "notifications-clear",
           "session-lock", "session-suspend", "session-logout",
           "session-reboot", "session-poweroff")


def plain(value, limit=4096):
    text = html.unescape(re.sub(r"<[^>]*>", "", str(value)))
    return text.replace("\x00", "")[:limit]


def history(text):
    """Dunst typed values -> inert presentation. Never invent callable actions."""
    value = json.loads(text)
    if not isinstance(value, dict):
        raise Error("Historial de Dunst inválido")
    groups = value.get("data")
    if not isinstance(groups, list) or any(not isinstance(g, list) for g in groups):
        raise Error("Historial de Dunst inválido")
    rows, seen = [], set()
    for group in groups:
        for item in group:
            if not isinstance(item, dict):
                continue

            def field(name, default=""):
                value = item.get(name, default)
                return value.get("data", default) if isinstance(value, dict) else value

            nid = str(field("id"))
            if not re.fullmatch(r"[0-9]{1,10}", nid) or int(nid) == 0 or int(nid) > 2**32 - 1 or nid in seen:
                continue
            seen.add(nid)
            rows.append(dict(id=nid, appName=plain(field("appname"), 128),
                             summary=plain(field("summary"), 512), body=plain(field("body")),
                             urgency=str(field("urgency", "normal")).lower(), actions=[]))
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
    def __init__(self, runner=None, available=None, environ=None, power_root=None, fixture=False,
                 launcher=None):
        self.env = keys.host_environment(os.environ if environ is None else environ)
        self.runner = runner or self.command
        # Session actions (lock, suspend, power) may outlive this process.
        self.launcher = launcher or (self.launch if runner is None else runner)
        self.available = available or (lambda name: shutil.which(name, path=self.env.get("PATH")))
        self.power_root = Path(power_root or "/sys/class/power_supply")
        self.fixture = fixture

    def command(self, argv):
        try:
            result = subprocess.run(argv, env=self.env, capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired as exc:
            raise Error("El proveedor no respondió a tiempo") from exc
        except OSError as exc:
            raise Error("Proveedor no disponible: " + argv[0]) from exc
        if result.returncode:
            raise Error("El proveedor rechazó la operación: " + argv[0])
        return result.stdout.strip()

    def launch(self, argv):
        """Start a session action without waiting for it to finish.

        A command that is still running after a short grace period (suspend
        blocks until resume) counts as accepted; one that exits with an error
        inside it is reported.
        """
        try:
            process = subprocess.Popen(argv, env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=True)
        except OSError as exc:
            raise Error("Proveedor no disponible: " + argv[0]) from exc
        try:
            code = process.wait(timeout=0.6)
        except subprocess.TimeoutExpired:
            return ""
        if code:
            raise Error("El proveedor rechazó la operación: " + argv[0])
        return ""

    def require(self, name):
        if not self.available(name):
            raise Error("No disponible: " + name)

    def network(self):
        self.require("nmcli")
        enabled = self.runner(["nmcli", "-t", "-f", "WIFI", "radio"])
        if enabled not in ("enabled", "disabled"):
            raise Error("Estado Wi-Fi inválido")
        devices = []
        for line in self.runner(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION",
                                 "device", "status"]).splitlines():
            fields = nmfields(line)
            if len(fields) == 4:
                devices.append(dict(zip(("device", "type", "state", "connection"), fields)))
        saved = []
        for line in self.runner(["nmcli", "-t", "-f", "UUID,NAME,TYPE", "connection", "show"]).splitlines():
            fields = nmfields(line)
            if len(fields) == 3 and re.fullmatch(r"[0-9a-fA-F-]{36}", fields[0]):
                saved.append(dict(uuid=fields[0], name=plain(fields[1], 128), type=fields[2]))
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
        level = percent(self.runner(["dunstctl", "get-pause-level"]))
        return dict(available=True, pauseLevel=level, paused=level > 0,
                    items=history(self.runner(["dunstctl", "history"])))

    def session(self):
        self.require("gdbus")
        result = {}
        for name, key in (("Suspend", "canSuspend"), ("Reboot", "canReboot"), ("PowerOff", "canPowerOff")):
            text = self.runner(["gdbus", "call", "--system", "--dest", "org.freedesktop.login1",
                                "--object-path", "/org/freedesktop/login1", "--method",
                                "org.freedesktop.login1.Manager.Can" + name]).strip()
            # "yes" is immediate; "challenge" is allowed after graphical polkit auth.
            result[key] = text in ("('yes',)", "('challenge',)")
        return dict(available=True, canLock=True, canLogout=True, **result)

    def snapshot(self, domains):
        result = {}
        for domain in domains:
            if domain not in DOMAINS:
                raise Error("Proveedor desconocido")
            try:
                result[domain] = getattr(self, domain)()
            except (Error, ValueError, TypeError, KeyError, OSError) as exc:
                result[domain] = dict(available=False, error=str(exc) if isinstance(exc, Error)
                                      else "Respuesta del proveedor inválida")
        return result

    def perform(self, action, value=""):
        """Validate from fresh state; one selected backend, no fallback after failure."""
        if action not in ACTIONS:
            raise Error("Acción desconocida")
        domain = action.partition("-")[0]
        before = getattr(self, domain)()
        command = self.plan(action, value, before)
        result = dict(ok=True, applied=not self.fixture, simulated=self.fixture, domain=domain)
        if domain == "session":
            self.launcher(command)
            result["state"] = before
            return result
        self.runner(command)
        after = self.snapshot([domain])[domain]
        result["state"] = after
        if not after["available"]:
            result["warning"] = "Acción enviada; no se pudo comprobar el estado final"
        return result

    def plan(self, action, value, state):
        if not state.get("available"):
            raise Error(state.get("error") or "Proveedor no disponible")
        if action == "network-toggle":
            return ["nmcli", "radio", "wifi", "off" if state["enabled"] else "on"]
        if action == "network-connect":
            if value not in {row["uuid"] for row in state["saved"]}:
                raise Error("La conexión ya no está disponible")
            return ["nmcli", "--wait", "2", "connection", "up", "uuid", value]
        if action == "bluetooth-toggle":
            return ["bluetoothctl", "power", "off" if state["enabled"] else "on"]
        if action in ("bluetooth-connect", "bluetooth-disconnect"):
            if value not in {row["address"] for row in state["devices"]}:
                raise Error("El dispositivo no está emparejado")
            return ["bluetoothctl", "connect" if action.endswith("connect") else "disconnect", value]
        if action == "notifications-pause":
            return ["dunstctl", "set-pause-level", "0" if state["paused"] else "100"]
        if action == "notifications-remove":
            if value not in {row["id"] for row in state["items"]}:
                raise Error("El aviso ya no está en el historial")
            return ["dunstctl", "history-rm", value]
        if action == "notifications-clear":
            if not state["items"]:
                raise Error("No hay avisos en el historial")
            return ["dunstctl", "history-clear"]
        if action == "session-lock":
            self.require("wysun")
            return ["wysun", "lock"]
        if action == "session-suspend":
            if not state["canSuspend"]:
                raise Error("La sesión no permite suspender ahora")
            self.require("wysun")
            return ["wysun", "lock", "--suspend"]
        if action == "session-logout":
            if not state["canLogout"]:
                raise Error("La sesión no permite cerrar la sesión")
            self.require("hyprctl")
            return ["hyprctl", "dispatch", "hl.dsp.exit()"]
        if action == "session-reboot":
            if not state["canReboot"]:
                raise Error("La sesión no permite reiniciar ahora")
            self.require("systemctl")
            return ["systemctl", "reboot"]
        if action == "session-poweroff":
            if not state["canPowerOff"]:
                raise Error("La sesión no permite apagar ahora")
            self.require("systemctl")
            return ["systemctl", "poweroff"]
        raise Error("Acción desconocida")


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
        provider = fixture_provider(args.fixture) if args.fixture else Providers()
        if args.operation == "snapshot":
            result = dict(ok=True, states=provider.snapshot(args.name.split(",")))
        else:
            result = provider.perform(args.name, args.value)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (Error, OSError, ValueError, TypeError, KeyError):
        # No raw backend diagnostics, notification bodies or private metadata.
        print(json.dumps(dict(ok=False,
                              error="No se pudo completar la operación. Actualiza el panel y vuelve a intentar."),
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
