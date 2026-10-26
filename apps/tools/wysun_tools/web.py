"""Project-aware web workflow; never installs dependencies implicitly."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import signal
import socket
from .common import (ToolError, check, emit, entry, executable, plan, port,
                     read_json, report, report_flags, require, run)

LOCKS = {"pnpm-lock.yaml": "pnpm", "package-lock.json": "npm",
         "npm-shrinkwrap.json": "npm", "yarn.lock": "yarn", "bun.lock": "bun",
         "bun.lockb": "bun"}


def project(directory: Path) -> tuple[Path, dict, str, list[str]]:
    root = directory.expanduser().resolve()
    package = read_json(root / "package.json")
    if not isinstance(package, dict):
        raise ToolError(f"No hay package.json válido en {root}. Usa --directory para elegir el proyecto.")
    locks = [name for name in LOCKS if (root / name).is_file()]
    managers = {LOCKS[name] for name in locks}
    declared = str(package.get("packageManager", "")).split("@")[0]
    if declared and declared not in {"npm", "pnpm", "yarn", "bun"}:
        raise ToolError("packageManager no está soportado: " + declared)
    if len(managers) > 1 or (declared and managers and declared not in managers):
        raise ToolError("Gestores o lockfiles incompatibles: " + ", ".join(locks))
    return root, package, declared or (next(iter(managers)) if managers else "npm"), locks


def framework(package: dict) -> str:
    deps = dict(package.get("dependencies", {}), **package.get("devDependencies", {}))
    return next((name for name in ("next", "vite", "astro", "nuxt") if name in deps), "custom")


def script_command(package: dict, manager: str, task: str, extras: list[str],
                   dev_port: int | None = None, host: str | None = None) -> list[str]:
    scripts = package.get("scripts", {})
    if task not in scripts:
        raise ToolError(f"No existe el script '{task}'. Disponibles: " + ", ".join(sorted(scripts)))
    options = list(extras)
    if dev_port or host:
        fw = framework(package)
        if task != "dev" or fw not in {"next", "vite", "astro", "nuxt"}:
            raise ToolError("--port y --host requieren dev con Next, Vite, Astro o Nuxt. Otros argumentos van después de --.")
        if dev_port:
            options += ["--port", str(dev_port)]
        if host:
            options += ["--hostname" if fw == "next" else "--host", host]
        if fw == "vite" and dev_port:
            options += ["--strictPort"]
    command = [manager, "run", task]
    return command + ((["--"] if manager == "npm" else []) + options if options else [])


def env_keys(path: Path) -> tuple[set[str], list[str]]:
    keys, duplicates = set(), []
    if not path.is_file():
        return keys, duplicates
    for line in path.read_text().splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_]\w*)\s*=", line)
        if match:
            if match[1] in keys:
                duplicates.append(match[1])
            keys.add(match[1])
    return keys, duplicates


def doctor(args) -> int:
    result = report("web-dev doctor")
    for tool in ("node", "npm", "pnpm", "git", "python3"):
        location = executable(tool)
        check(result, tool, "pass" if location else ("fail" if tool in {"node", "git"} else "info"),
              location or "No instalado")
    try:
        root, package, manager, locks = project(args.directory)
        result["data"].update(directory=str(root), package_manager=manager,
                              framework=framework(package), scripts=sorted(package.get("scripts", {})))
        check(result, "Gestor del proyecto", "pass" if executable(manager) else "fail", manager)
        check(result, "Dependencias reproducibles", "pass" if locks else "warn", ", ".join(locks) or "No hay lockfile")
        check(result, "Dependencias locales", "pass" if (root / "node_modules").is_dir() else "warn",
              "Instaladas" if (root / "node_modules").is_dir() else "Ejecuta la instalación del gestor elegido")
        if (root / ".env.example").is_file():
            expected, _ = env_keys(root / ".env.example")
            actual, duplicates = env_keys(root / ".env")
            missing = sorted(expected - actual)
            check(result, "Variables de entorno", "warn" if missing or duplicates else "pass",
                  "Faltan: " + ", ".join(missing) if missing else
                  ("Duplicadas: " + ", ".join(duplicates) if duplicates else "Solo se revisaron nombres"))
    except ToolError as error:
        check(result, "Proyecto", "fail", str(error))
    return emit(result, args)


def tasks(args) -> int:
    root, package, manager, _ = project(args.directory)
    extras = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    command = script_command(package, manager, args.command, extras, args.port, args.host)
    if args.port and not args.dry_run:
        try:
            family = socket.AF_INET6 if ":" in (args.host or "") else socket.AF_INET
            with socket.socket(family) as probe:
                probe.bind((args.host or "127.0.0.1", args.port))
        except PermissionError:
            raise ToolError("No hay permisos para comprobar el puerto en este entorno.") from None
        except OSError:
            raise ToolError(f"El puerto {args.port} está ocupado o la dirección no está disponible. Usa web-dev ports.") from None
    if args.dry_run:
        print(f"Directorio: {root}")
        plan(command)
        return 0
    require(manager)
    os.chdir(root)
    os.execvp(command[0], command)
    return 0


def ports(args) -> int:
    result = report("web-dev ports")
    command = [require("ss"), "-H", "-ltnp"]
    if args.port:
        command += [f"sport = :{args.port}"]
    result["data"]["listeners"] = run(command).stdout.strip().splitlines()
    return emit(result, args)


def stop(args) -> int:
    command = [require("ss"), "-H", "-ltnp", f"sport = :{args.port}"]
    pids = sorted({int(pid) for pid in re.findall(r"pid=(\d+)", run(command).stdout)})
    if not pids:
        raise ToolError(f"No hay procesos visibles escuchando en {args.port}.")
    identities = {}
    for pid in pids:
        identities[pid] = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")",1)[1].split()[19]
        if (Path("/proc") / str(pid)).stat().st_uid != os.getuid() or pid == os.getpid():
            raise ToolError("Hay procesos ajenos en el puerto; no se enviaron señales.")
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise ToolError("Este sistema no admite señales con identidad de proceso protegida.")
    handles = []
    try:
        for pid in pids:
            handle = os.pidfd_open(pid)
            handles.append((pid, handle))
            identity = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")",1)[1].split()[19]
            if identity != identities[pid] or (Path("/proc") / str(pid)).stat().st_uid != os.getuid():
                raise ToolError("El propietario del proceso cambió.")
        current = {int(pid) for pid in re.findall(r"pid=(\d+)", run(command).stdout)}
        if not set(pids) <= current:
            raise ToolError("Cambió el proceso que escucha; vuelve a consultar el puerto.")
        for pid, handle in handles:
            if args.dry_run:
                print(f"PLAN SIGTERM PID {pid} · puerto {args.port}")
            else:
                signal.pidfd_send_signal(handle, signal.SIGTERM)
                print(f"SIGTERM enviado a PID {pid}.")
    finally:
        for _, handle in handles:
            os.close(handle)
    return 0


def environment(args) -> int:
    root = args.directory.expanduser().resolve()
    if not (root / args.example).is_file():
        raise ToolError(f"No existe {args.example}.")
    expected, _ = env_keys(root / args.example)
    actual, duplicates = env_keys(root / args.file)
    missing = sorted(expected - actual)
    public_secrets = sorted(key for key in actual if key.startswith(("VITE_", "NEXT_PUBLIC_", "NUXT_PUBLIC_"))
                            and re.search("SECRET|PASSWORD|PRIVATE|TOKEN", key))
    result = report("web-dev env")
    check(result, "Variables requeridas", "fail" if missing else "pass", ", ".join(missing))
    check(result, "Variables duplicadas", "warn" if duplicates else "pass", ", ".join(duplicates))
    check(result, "Nombres sensibles públicos", "warn" if public_secrets else "pass", ", ".join(public_secrets))
    result["data"]["extra_keys"] = sorted(actual - expected)
    return emit(result, args)


def init(args) -> int:
    target = args.directory.expanduser().resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ToolError("La carpeta de destino no está vacía.")
    files = {
        "index.html": '<!doctype html>\n<html lang="es-MX"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Proyecto web</title><link rel="stylesheet" href="style.css"><main><h1>Proyecto web</h1><p>Listo para desarrollar.</p></main><script src="main.js"></script></html>\n',
        "style.css": 'body{margin:0;background:#141416;color:#ededf0;font:16px/1.6 system-ui}main{max-width:960px;margin:12vh auto;padding:24px}h1{font-size:clamp(2rem,6vw,4rem);letter-spacing:-.04em}\n',
        "main.js": '"use strict";\n',
        ".gitignore": "node_modules/\ndist/\n.env\n.env.*\n!.env.example\n",
        "README.md": "# Proyecto web\n\nEjecuta web-dev serve --directory . --port 5173.\n",
    }
    if args.dry_run:
        print(f"PLAN Crear {target}: " + ", ".join(files))
        return 0
    target.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        with (target / name).open("x") as stream:
            stream.write(content)
    print(f"Proyecto creado: {target}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="web-dev", description="Desarrollo web reproducible, diagnóstico y tareas del proyecto.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("doctor", help="Revisar proyecto y dependencias")
    p.add_argument("-C", "--directory", type=Path, default=Path.cwd())
    report_flags(p); p.set_defaults(fn=doctor)
    for task in ("dev", "build", "test", "lint", "typecheck"):
        p = sub.add_parser(task, help=f"Ejecutar scripts.{task} con el gestor del proyecto")
        p.add_argument("-C", "--directory", type=Path, default=Path.cwd())
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--port", type=port)
        p.add_argument("--host", help="Dirección explícita del servidor dev")
        p.add_argument("arguments", nargs=argparse.REMAINDER)
        p.set_defaults(fn=tasks)
    p = sub.add_parser("ports", help="Consultar servidores TCP locales")
    p.add_argument("--port", type=port); report_flags(p); p.set_defaults(fn=ports)
    p = sub.add_parser("stop", help="Enviar SIGTERM a los procesos propios que escuchan en un puerto")
    p.add_argument("--port", type=port, required=True); p.add_argument("--dry-run", action="store_true"); p.set_defaults(fn=stop)
    p = sub.add_parser("env", help="Comparar nombres de variables, sin mostrar valores")
    p.add_argument("-C", "--directory", type=Path, default=Path.cwd())
    p.add_argument("--example", type=Path, default=Path(".env.example"))
    p.add_argument("--file", type=Path, default=Path(".env")); report_flags(p); p.set_defaults(fn=environment)
    p = sub.add_parser("init", help="Crear un proyecto estático sin descargar dependencias")
    p.add_argument("directory", type=Path); p.add_argument("--dry-run", action="store_true"); p.set_defaults(fn=init)
    p = sub.add_parser("serve", help="Servidor estático con rutas restringidas")
    from .transfer import server_flags, serve
    server_flags(p, uploads=False); p.set_defaults(fn=serve)
    p = sub.add_parser("check", help="Revisar estado HTTP y cabeceras")
    from .security import http_flags, audit_http
    http_flags(p); p.set_defaults(fn=audit_http)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    entry(main)
