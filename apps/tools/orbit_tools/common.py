"""Bounded subprocesses, private reports and consistent CLI output."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


class ToolError(Exception):
    """Expected actionable failure, without a traceback."""


def executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for folder in ("/usr/sbin", "/sbin"):
        candidate = Path(folder) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def require(name: str) -> str:
    found = executable(name)
    if not found:
        raise ToolError(f"Falta {name}. Consulta el comando doctor para las dependencias.")
    return found


def redact(text: str) -> str:
    text = re.sub(r"(?i)((?:password|passwd|secret|token|api[_-]?key|authorization)\s*[:=]\s*)[^\s,;]+", r"\1[oculto]", text)
    text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [oculto]", text)
    text = re.sub(r"://[^/\s]+:[^@\s]+@", "://[oculto]@", text)
    text = re.sub(r"\b(?:ghp_|github_pat_|sk_live_|xox[baprs]-)[A-Za-z0-9_-]+", "[oculto]", text)
    return text


def run(argv: list[str], *, timeout: float = 30, check: bool = True,
        capture: bool = True, input: str | None = None,
        cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(argv, text=True, input=input, cwd=cwd, timeout=timeout,
                                capture_output=capture, check=False)
    except FileNotFoundError:
        raise ToolError(f"No se encontró {argv[0]}.") from None
    except subprocess.TimeoutExpired:
        raise ToolError(f"{Path(argv[0]).name} superó el tiempo límite de {timeout:g} s.") from None
    if check and result.returncode:
        detail = redact((result.stderr or "").strip())[-1200:]
        raise ToolError(f"{Path(argv[0]).name} terminó con código {result.returncode}" +
                        (f": {detail}" if detail else "."))
    return result


def private_write(path: Path, content: str | bytes, *, overwrite: bool = True) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content.encode() if isinstance(content, str) else content)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except (ValueError, UnicodeError):
        raise ToolError(f"JSON inválido: {path}") from None


def report(command: str) -> dict:
    return {"schema_version": 1, "command": command,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "checks": [], "data": {}}


def check(result: dict, name: str, status: str, detail: str = "") -> None:
    result["checks"].append({"name": name, "status": status, "detail": redact(detail)})


def report_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Salida JSON para automatización")
    parser.add_argument("--output", type=Path, help="Guardar informe JSON privado")
    parser.add_argument("--force-output", action="store_true", help="Reemplazar un informe existente")
    parser.add_argument("--strict", action="store_true", help="Las advertencias también producen código 1")


def emit(result: dict, args) -> int:
    def scrub(value):
        if isinstance(value,str): return redact(value)
        if isinstance(value,list): return [scrub(v) for v in value]
        if isinstance(value,dict): return {k:scrub(v) for k,v in value.items()}
        return value
    result = scrub(result)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if getattr(args, "output", None):
        try:
            private_write(args.output, payload, overwrite=args.force_output)
        except FileExistsError:
            raise ToolError(f"El informe ya existe: {args.output}. Usa --force-output para reemplazarlo.") from None
    if getattr(args, "json", False):
        print(payload, end="")
    else:
        for item in result["checks"]:
            print(f"{item['status'].upper():5} {item['name']}" +
                  (f" · {item['detail']}" if item["detail"] else ""))
        for key, value in result["data"].items():
            print(f"{key}: " + (json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)))
        if getattr(args, "output", None):
            print(f"Informe: {args.output}")
    failures = {"fail", "warn"} if getattr(args, "strict", False) else {"fail"}
    return int(any(item["status"] in failures for item in result["checks"]))


def positive(value: str) -> float:
    try:
        parsed = float(value)
        if not 0 < parsed <= 3600:
            raise ValueError()
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError("Usa un número mayor que 0 y no mayor que 3600.") from None


def port(value: str) -> int:
    try:
        parsed = int(value)
        if not 1 <= parsed <= 65535:
            raise ValueError()
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError("El puerto debe estar entre 1 y 65535.") from None


def plan(argv: list[str]) -> None:
    print("PLAN " + redact(shlex.join(argv)))


def entry(fn) -> None:
    try:
        raise SystemExit(fn())
    except (ToolError, OSError) as error:
        print("ERROR " + redact(str(error)), file=sys.stderr)
        raise SystemExit(2) from None
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        raise SystemExit(130) from None
