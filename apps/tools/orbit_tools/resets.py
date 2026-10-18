#!/usr/bin/env python3
"""Display countdowns to Codex/Claude reset times.

Config file: $XDG_CONFIG_HOME/orbit/resets/accounts.json.
Legacy accounts are copied once on first use, without modifying the original.

Each entry is an object with:
  - name: human label for the account
  - service: codex or claude (or any label you want)
  - reset_at: ISO 8601 datetime, with or without timezone
  - note: optional free text
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import shlex
import time
from .common import private_write, ToolError
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "orbit/resets"
CONFIG_FILE = APP_DIR / "accounts.json"

def color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


GREEN = "32"
YELLOW = "33"
RED = "31"
BLUE = "34"
DIM = "2"
BOLD = "1"


@dataclass
class ResetPoint:
    label: str
    reset_at: str


@dataclass
class Account:
    name: str
    service: str
    resets: list[ResetPoint]
    note: str = ""


def ensure_config() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return
    candidates = [Path(os.environ.get("XDG_CONFIG_HOME",str(Path.home()/".config"))) / "dotifails/rezets/accounts.json",Path.home()/"scripts/.rezets/accounts.json"]
    legacy = next((p for p in candidates if p.is_file()),candidates[-1])
    if legacy.is_file() and CONFIG_FILE != legacy:
        text = legacy.read_text(encoding="utf-8")
        if not isinstance(json.loads(text), list):
            raise ToolError("El archivo anterior no contiene una lista; se conserva sin cambios.")
        private_write(CONFIG_FILE, text, overwrite=False)
    else:
        private_write(CONFIG_FILE, "[]\n", overwrite=False)


def load_accounts() -> list[Account]:
    ensure_config()
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config invalida: {CONFIG_FILE}\n{exc}") from exc

    if not isinstance(raw, list):
        raise SystemExit(f"Config invalida: se esperaba una lista en {CONFIG_FILE}")

    accounts: list[Account] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"Entrada invalida en posicion {idx}: se esperaba un objeto")
        try:
            resets_raw = item.get("resets")
            if resets_raw is None and "reset_at" in item:
                resets_raw = [{"label": "reset", "reset_at": item["reset_at"]}]
            if not isinstance(resets_raw, list) or not resets_raw:
                raise SystemExit(f"Entrada {idx} incompleta: falta resets/reset_at")

            resets: list[ResetPoint] = []
            for r_idx, reset in enumerate(resets_raw, start=1):
                if isinstance(reset, str):
                    resets.append(ResetPoint(label=f"reset {r_idx}", reset_at=reset))
                    continue
                if not isinstance(reset, dict):
                    raise SystemExit(
                        f"Entrada {idx}, reset {r_idx}: se esperaba un objeto o string"
                    )
                if "reset_at" not in reset:
                    raise SystemExit(f"Entrada {idx}, reset {r_idx}: falta reset_at")
                resets.append(
                    ResetPoint(
                        label=str(reset.get("label", f"reset {r_idx}")).strip() or f"reset {r_idx}",
                        reset_at=str(reset["reset_at"]).strip(),
                    )
                )

            accounts.append(
                Account(
                    name=str(item["name"]).strip(),
                    service=str(item["service"]).strip(),
                    resets=resets,
                    note=str(item.get("note", "")).strip(),
                )
            )
        except KeyError as exc:
            raise SystemExit(f"Entrada {idx} incompleta: falta {exc.args[0]}") from exc

    return accounts


def save_accounts(accounts: list[Account]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "name": item.name,
            "service": item.service,
            "resets": [
                {
                    "label": reset.label,
                    "reset_at": reset.reset_at,
                }
                for reset in item.resets
            ],
            "note": item.note,
        }
        for item in accounts
    ]
    if CONFIG_FILE.exists():
        private_write(CONFIG_FILE.with_suffix(".json.bak"), CONFIG_FILE.read_bytes())
    private_write(CONFIG_FILE, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def parse_time_of_day(value: str, base_date: datetime) -> datetime:
    raw = value.strip().lower().replace(" ", "")
    match = re.fullmatch(r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?(?P<ampm>am|pm)?", raw)
    if not match:
        raise ValueError(value)

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    if minute > 59:
        raise ValueError("Los minutos deben estar entre 0 y 59.")
    ampm = match.group("ampm")
    if ampm:
        if hour < 1 or hour > 12:
            raise ValueError(value)
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
    elif hour > 23:
        raise ValueError(value)

    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_month_day_time(value: str, now: datetime) -> datetime:
    cleaned = value.strip()
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    month_day_patterns = [
        r"^(?P<time>\d{1,2}:\d{2}(?:\s*[ap]m)?)\s+on\s+(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)$",
        r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),?\s+(?P<time>.+)$",
        r"^(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+),?\s+(?P<time>.+)$",
    ]

    for pattern in month_day_patterns:
        match = re.fullmatch(pattern, cleaned)
        if not match:
            continue

        month_name = match.group("month").lower()
        month_map = {
            "jan": 1, "january": 1,
            "feb": 2, "february": 2,
            "mar": 3, "march": 3,
            "apr": 4, "april": 4,
            "may": 5,
            "jun": 6, "june": 6,
            "jul": 7, "july": 7,
            "aug": 8, "august": 8,
            "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10,
            "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }
        if month_name not in month_map:
            raise ValueError(value)

        month = month_map[month_name]
        day = int(match.group("day"))
        time_part = match.group("time")
        year = now.year
        base = now.replace(year=year, month=month, day=day)
        dt = parse_time_of_day(time_part, base)
        if dt < now:
            dt = dt.replace(year=year + 1)
        return dt

    raise ValueError(value)


def parse_datetime(value: str) -> datetime:
    value = value.strip()
    if not value:
        raise ValueError("datetime vacio")

    if len(value) == 10 and value.count("-") == 2:
        value = f"{value}T00:00:00"
    candidate = value.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        now = datetime.now().astimezone()
        time_match = re.fullmatch(r"\d{1,2}:\d{2}(?:\s*[ap]m)?", value.strip(), re.IGNORECASE)
        if time_match:
            dt = parse_time_of_day(value, now)
            if dt < now:
                dt += timedelta(days=1)
        else:
            try:
                dt = parse_month_day_time(value, now)
            except ValueError as inner_exc:
                raise ValueError(
                    "Usa algo como 2026-04-29T00:00:00-07:00, 10:22, 10:10am, o May 2, 6pm"
                ) from inner_exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def human_delta(delta_seconds: int) -> str:
    future = delta_seconds >= 0
    seconds = abs(delta_seconds)

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")

    text = " ".join(parts)
    return f"faltan {text}" if future else f"paso hace {text}"


def format_reset_time(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def status_label(delta_seconds: int) -> str:
    if delta_seconds < 0:
        return color("PASADO", RED)
    if delta_seconds < 3600:
        return color("URGENTE", RED)
    if delta_seconds < 86400:
        return color("HOY", YELLOW)
    return color("OK", GREEN)


def print_table(accounts: list[Account]) -> None:
    rows: list[tuple[int, str, str, datetime, str, str]] = []
    now = datetime.now().astimezone()
    for account in accounts:
        for reset in account.resets:
            dt = parse_datetime(reset.reset_at)
            delta = int((dt - now).total_seconds())
            rows.append((delta, account.name, account.service, dt, reset.label, account.note))

    if not rows:
        print(color("No hay cuentas guardadas.", YELLOW))
        print(f"Agrega una con: {color('rezets add <nombre> <servicio> <reset_at> [nota]', BLUE)}")
        return

    header = f"{'CUENTA':18} {'SERVICIO':10} {'TIPO':14} {'RESET':26} {'RESTA':20} {'ESTADO':8}"
    print(color(header, BOLD))
    print(color("-" * len(header), DIM))

    rows.sort(key=lambda item: item[0])

    for delta, name, service, dt, label, note in rows:
        remaining = human_delta(delta)
        reset_str = format_reset_time(dt)
        state = status_label(delta)
        print(
            f"{name[:18]:18} "
            f"{service[:10]:10} "
            f"{label[:14]:14} "
            f"{reset_str[:26]:26} "
            f"{remaining[:20]:20} "
            f"{state:8}"
        )


def add_account(args: argparse.Namespace) -> None:
    accounts = load_accounts()
    note = " ".join(args.note).strip() if args.note else ""
    entry = Account(
        name=args.name.strip(),
        service=args.service.strip(),
        resets=[ResetPoint(label="reset", reset_at=args.reset_at.strip())],
        note=note,
    )
    parse_datetime(entry.resets[0].reset_at)
    if not entry.name or not entry.service:
        raise ValueError("Nombre y servicio son obligatorios.")
    if any(a.name.casefold() == entry.name.casefold() for a in accounts):
        raise ValueError("Ya existe una cuenta con ese nombre.")
    accounts.append(entry)
    save_accounts(accounts)
    print(color(f"Guardado: {entry.name} ({entry.service})", GREEN))
    print(f"Archivo: {CONFIG_FILE}")


def remove_account(args: argparse.Namespace) -> None:
    accounts = load_accounts()
    if not accounts:
        print(color("No hay cuentas para borrar.", YELLOW))
        return

    target = args.target.strip().lower()
    index: int | None = None
    if target.isdigit():
        idx = int(target)
        if 1 <= idx <= len(accounts):
            index = idx - 1

    updated: list[Account] = []
    removed = False
    for pos, account in enumerate(accounts):
        if index is not None and pos == index:
            removed = True
            continue
        if account.name.lower() == target:
            removed = True
            continue
        updated.append(account)

    if not removed:
        print(color(f"No encontre la cuenta '{args.target}'.", RED))
        return

    save_accounts(updated)
    print(color(f"Eliminada la cuenta '{args.target}'.", GREEN))


def edit_config(_args: argparse.Namespace) -> None:
    ensure_config()
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    previous = CONFIG_FILE.read_bytes()
    result = subprocess.run([*shlex.split(editor), str(CONFIG_FILE)], check=False)
    if result.returncode:
        raise ToolError(f"El editor terminó con código {result.returncode}.")
    try:
        accounts = load_accounts()
        for account in accounts:
            for reset in account.resets:
                parse_datetime(reset.reset_at)
    except (SystemExit, ValueError):
        private_write(CONFIG_FILE.with_suffix(".json.invalid"), CONFIG_FILE.read_bytes())
        private_write(CONFIG_FILE, previous)
        raise ToolError("Edición inválida. Se restauró el archivo y se guardó la edición en .json.invalid.") from None
    private_write(CONFIG_FILE.with_suffix(".json.bak"), previous)
    CONFIG_FILE.chmod(0o600)


def init_config(_args: argparse.Namespace) -> None:
    ensure_config()
    print(color(f"Archivo listo: {CONFIG_FILE}", GREEN))
    print("Editalo con:")
    print(f"  {color('rezets edit', BLUE)}")


def infer_service(block: str, fallback: str = "unknown") -> str:
    lowered = block.lower()
    if "context window" in lowered or "weekly limit" in lowered:
        return "codex"
    if "current session" in lowered or "current week" in lowered:
        return "claude"
    return fallback


def parse_pasted_blocks(text: str, service_fallback: str = "unknown") -> list[Account]:
    text = re.sub(r'(?<!^)(?=\[[A-Za-z0-9][A-Za-z0-9._ -]*\])', "\n", text)
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        header = re.fullmatch(r"\[(.+?)\]", line.strip())
        if header:
            if current:
                blocks.append(current)
            current = [header.group(1).strip()]
            continue
        if current:
            current.append(line.rstrip())
    if current:
        blocks.append(current)

    accounts: list[Account] = []
    for block_lines in blocks:
        if not block_lines:
            continue
        name = block_lines[0]
        body = block_lines[1:]
        block_text = "\n".join(body)
        service = infer_service(block_text, service_fallback)
        resets: list[ResetPoint] = []
        pending_label: str | None = None

        for raw_line in body:
            line = raw_line.strip()
            if not line:
                continue

            combined = re.search(r"^(?P<label>[^:]+):.*?\(resets\s+(?P<when>[^)]+)\)", line, re.IGNORECASE)
            if combined:
                resets.append(
                    ResetPoint(
                        label=combined.group("label").strip(),
                        reset_at=combined.group("when").strip(),
                    )
                )
                pending_label = None
                continue

            label_only = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9 \-_/]+)", line)
            if label_only and "reset" not in line.lower() and not line.lower().startswith("resets "):
                pending_label = line
                continue

            standalone = re.search(r"^resets\s+(?P<when>[^()]+)", line, re.IGNORECASE)
            if standalone:
                label = pending_label or f"reset {len(resets) + 1}"
                resets.append(
                    ResetPoint(
                        label=label.strip(),
                        reset_at=standalone.group("when").strip().rstrip(","),
                    )
                )
                pending_label = None

        if resets:
            accounts.append(Account(name=name, service=service, resets=resets))

    return accounts


def paste_import(args: argparse.Namespace) -> None:
    ensure_config()
    if sys.stdin.isatty():
        print("Pega el texto del /status y termina con Ctrl-D:")
    text = sys.stdin.read()
    imported = parse_pasted_blocks(text, service_fallback=args.service or "unknown")
    if not imported:
        print(color("No pude detectar bloques con resets.", RED))
        return

    accounts = load_accounts()
    accounts.extend(imported)
    save_accounts(accounts)
    print(color(f"Importadas {len(imported)} cuentas.", GREEN))
    for item in imported:
        print(f" - {item.name} ({item.service}): {len(item.resets)} resets")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rezets",
        description="Muestra el tiempo restante para los resets de Codex y Claude.",
    )
    parser.add_argument("--config", type=Path, help="Archivo alternativo; no migra datos privados del usuario")
    parser.add_argument("--json", action="store_true", help="Estado estructurado")
    parser.add_argument("--service", dest="filter_service", help="Filtrar servicio al listar")
    parser.add_argument("--watch", type=float, help="Actualizar cada N segundos")
    sub = parser.add_subparsers(dest="command")

    parser.set_defaults(command="list")

    add_p = sub.add_parser("add", help="Agregar una cuenta")
    add_p.add_argument("name", help="Nombre corto de la cuenta")
    add_p.add_argument("service", help="codex, claude, u otro nombre")
    add_p.add_argument("reset_at", help="Fecha/hora ISO 8601 del reset")
    add_p.add_argument("note", nargs="*", help="Nota opcional")
    add_p.set_defaults(func=add_account)

    rm_p = sub.add_parser("rm", help="Eliminar una cuenta por nombre o numero")
    rm_p.add_argument("target", help="Nombre exacto o numero de la fila")
    rm_p.set_defaults(func=remove_account)

    edit_p = sub.add_parser("edit", help="Abrir el archivo de configuracion")
    edit_p.set_defaults(func=edit_config)

    init_p = sub.add_parser("init", help="Crear el archivo de configuracion si no existe")
    init_p.set_defaults(func=init_config)

    paste_p = sub.add_parser("paste", help="Importar texto pegado de /status")
    paste_p.add_argument("--service", default="unknown", help="Servicio por defecto si no se puede inferir")
    paste_p.set_defaults(func=paste_import)

    list_p = sub.add_parser("list", help="Mostrar estado")
    list_p.set_defaults(func=show_accounts)

    return parser


def show_accounts(args):
    accounts = load_accounts()
    if args.filter_service:
        accounts = [a for a in accounts if a.service.casefold() == args.filter_service.casefold()]
    if args.json:
        now = datetime.now().astimezone()
        values = [{"name": a.name, "service": a.service, "resets": [
            {"label": r.label, "reset_at": parse_datetime(r.reset_at).isoformat(),
             "remaining_seconds": int((parse_datetime(r.reset_at)-now).total_seconds())}
            for r in a.resets]} for a in accounts]
        print(json.dumps(values, ensure_ascii=False))
    else:
        print_table(accounts)


def main(argv=None) -> int:
    global CONFIG_FILE, APP_DIR
    args = build_parser().parse_args(argv)
    if args.config:
        CONFIG_FILE = args.config.expanduser().absolute()
        APP_DIR = CONFIG_FILE.parent
        if not CONFIG_FILE.exists():
            private_write(CONFIG_FILE, "[]\n", overwrite=False)
    if args.watch is not None and (args.watch < 1 or args.watch > 3600 or args.command != "list"):
        raise ToolError("--watch requiere list y un intervalo de 1 a 3600 segundos.")
    try:
        if args.command == "list":
            while True:
                if args.watch and sys.stdout.isatty(): print("\033[2J\033[H",end="")
                show_accounts(args)
                if not args.watch: break
                sys.stdout.flush(); time.sleep(args.watch)
        else:
            args.func(args)
        return 0
    except ValueError:
        raise ToolError("Fecha o configuración inválida; usa una fecha ISO 8601 con zona horaria.") from None
