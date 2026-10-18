"""Explicit-target audits with structured findings and no credential output."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from .common import (ToolError, check, emit, entry, executable, plan, port, positive,
                     report, report_flags, require, run)


def url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ToolError("Usa una URL HTTP(S) sin credenciales incrustadas.")
    try:
        parsed.port
    except ValueError:
        raise ToolError("Puerto inválido en la URL.") from None
    return value


def display_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class ValidatedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_flags(parser):
    parser.add_argument("url")
    parser.add_argument("--timeout", type=positive, default=10)
    parser.add_argument("--expect", type=int, help="Estado HTTP exacto esperado")
    parser.add_argument("--method", choices=("HEAD", "GET"), default="HEAD")
    report_flags(parser)


def audit_http(args) -> int:
    target = url(args.url)
    result = report("sec-audit http")
    opener = urllib.request.build_opener(ValidatedRedirect())
    started = time.monotonic()
    request = urllib.request.Request(target, headers={"User-Agent": "dotifails-audit/1.0"}, method=args.method)
    try:
        try:
            response = opener.open(request, timeout=args.timeout)
        except urllib.error.HTTPError as error:
            if error.code == 405 and args.method == "HEAD":
                response = opener.open(urllib.request.Request(target, method="GET"), timeout=args.timeout)
            else:
                response = error
        with response:
            status = response.code
            headers = response.headers
            final = response.geturl()
            elapsed = round((time.monotonic() - started) * 1000, 1)
        result["data"].update(url=display_url(target), final_url=display_url(final),
                              status=status, latency_ms=elapsed)
        check(result, "Estado HTTP", "pass" if (status == args.expect if args.expect else 200 <= status < 300) else "fail", str(status))
        secure = urllib.parse.urlsplit(final).scheme == "https"
        check(result, "Transporte HTTPS", "pass" if secure else "warn")
        required = ["Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy"]
        if secure:
            required += ["Strict-Transport-Security"]
        for name in required:
            value = headers.get(name, "")
            check(result, name, "pass" if value else "warn", value[:500])
        frame = headers.get("X-Frame-Options", "")
        csp = headers.get("Content-Security-Policy", "")
        check(result, "Política de marcos", "pass" if frame or "frame-ancestors" in csp.lower() else "warn",
              frame or ("CSP frame-ancestors" if "frame-ancestors" in csp.lower() else "No declarada"))
        if headers.get("X-Content-Type-Options") and headers.get("X-Content-Type-Options", "").lower().strip() != "nosniff":
            check(result, "Valor X-Content-Type-Options", "warn", "Se esperaba nosniff")
        if secure and headers.get("Strict-Transport-Security"):
            max_age = re.search(r"max-age\s*=\s*(\d+)", headers["Strict-Transport-Security"], re.I)
            check(result, "HSTS activo", "pass" if max_age and int(max_age[1]) > 0 else "warn")
        cookies = headers.get_all("Set-Cookie", [])
        result["data"]["cookies"] = {"count": len(cookies),
            "without_secure": sum("secure" not in c.lower().split(";")[1:] and
                                  not re.search(r";\s*secure(?:;|$)", c, re.I) for c in cookies),
            "without_httponly": sum(not re.search(r";\s*httponly(?:;|$)", c, re.I) for c in cookies)}
        if urllib.parse.urlsplit(target).scheme == "https" and not secure:
            check(result, "Redirección HTTPS a HTTP", "fail")
        check(result, "Alcance", "info", "Presencia de cabeceras; no equivale a una auditoría completa de la aplicación")
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as error:
        check(result, "Conexión", "fail", str(getattr(error, "reason", error)))
    return emit(result, args)


def hostname(value: str) -> str:
    if "/" in value or value.startswith("-") or not value or len(value) > 253:
        raise ToolError("Usa un host, dirección IP o dominio; no una opción o ruta.")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        encoded = value.rstrip(".").encode("idna").decode()
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", item)
                   for item in encoded.split(".")):
            raise ToolError("Nombre de host inválido.")
        return encoded


def audit_tls(args) -> int:
    host = hostname(args.host)
    result = report("sec-audit tls")
    context = ssl.create_default_context(cafile=str(args.ca_file) if args.ca_file else None)
    if args.allow_self_signed:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    context.set_alpn_protocols(["h2", "http/1.1"])
    try:
        with socket.create_connection((host, args.port), timeout=args.timeout) as tcp:
            with context.wrap_socket(tcp, server_hostname=args.server_name or host) as conn:
                cert = conn.getpeercert()
                der = conn.getpeercert(binary_form=True)
                result["data"].update(host=host, port=args.port, protocol=conn.version(),
                    cipher=conn.cipher()[0], alpn=conn.selected_alpn_protocol(),
                    certificate_sha256=hashlib.sha256(der).hexdigest())
                check(result, "Certificado y nombre", "warn" if args.allow_self_signed else "pass",
                      "Validación omitida explícitamente" if args.allow_self_signed else "Verificados")
                check(result, "TLS moderno", "pass" if conn.version() in {"TLSv1.2", "TLSv1.3"} else "warn", conn.version())
                if cert and cert.get("notAfter"):
                    remaining = (ssl.cert_time_to_seconds(cert["notAfter"]) - time.time()) / 86400
                    check(result, "Caducidad", "warn" if remaining < args.days else "pass", f"{remaining:.1f} días")
                    result["data"]["expires_at"] = cert["notAfter"]
                else:
                    check(result, "Caducidad", "info", "No disponible sin validación del certificado")
    except (OSError, ssl.SSLError) as error:
        check(result, "Conexión TLS", "fail", str(error))
    return emit(result, args)


def port_spec(value: str) -> str:
    if not re.fullmatch(r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*", value):
        raise ToolError("Usa puertos como 22,80,443 o 1-1024.")
    for item in value.split(","):
        numbers = list(map(int, item.split("-")))
        if any(n < 1 or n > 65535 for n in numbers) or numbers[0] > numbers[-1]:
            raise ToolError("Rango de puertos inválido.")
    return value


def nmap_command(args) -> list[str]:
    if "/" in args.target:
        try:
            network = ipaddress.ip_network(args.target, strict=False)
        except ValueError:
            raise ToolError("Red CIDR inválida.") from None
        if network.num_addresses > args.max_hosts:
            raise ToolError(f"La red supera --max-hosts {args.max_hosts}. Especifica un alcance menor.")
        target = str(network)
    else:
        target = hostname(args.target)
    command = ["nmap", "-sT", "-Pn", "-n", "--open", "--reason", "-T3",
               "--max-rate", str(args.rate), "--host-timeout", f"{max(1,int(args.timeout))}s",
               "-p", port_spec(args.ports), "-oX", "-"]
    if ":" in target:
        command.append("-6")
    if args.services:
        command += ["-sV", "--version-light"]
    return command + [target]


def parse_nmap(xml: str) -> list[dict]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        raise ToolError("Nmap no produjo XML válido.") from None
    hosts = []
    for host in root.findall("host"):
        addresses = [node.get("addr") for node in host.findall("address") if node.get("addrtype") != "mac"]
        ports = []
        for node in host.findall("ports/port"):
            state, service = node.find("state"), node.find("service")
            ports.append({"port": int(node.get("portid")), "protocol": node.get("protocol"),
                "state": state.get("state") if state is not None else "unknown",
                "service": service.get("name") if service is not None else None,
                "product": service.get("product") if service is not None else None,
                "version": service.get("version") if service is not None else None})
        hosts.append({"addresses": addresses, "ports": ports})
    return hosts


def audit_ports(args) -> int:
    command = nmap_command(args)
    if args.dry_run:
        plan(command)
        return 0
    command[0] = require("nmap")
    result = report("sec-audit ports")
    xml = run(command, timeout=args.timeout + 5).stdout
    result["data"]["hosts"] = parse_nmap(xml)
    check(result, "Escaneo TCP", "pass", "Conexiones TCP; no se ejecutaron scripts NSE")
    return emit(result, args)


SECRET_PATTERNS = {
    "clave privada": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "clave AWS": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "token GitHub": re.compile(r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "token Slack": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "clave Google": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
}


def project_findings(root: Path, *, include_untracked=False) -> tuple[list[dict], int]:
    command = [require("git"), "-C", str(root), "ls-files", "-z", "--cached"]
    if include_untracked:
        command += ["--others", "--exclude-standard"]
    names = run(command).stdout.split("\0")
    findings, scanned, budget = [], 0, 64 * 1024 * 1024
    for name in dict.fromkeys(names):
        if not name:
            continue
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
            continue
        if any(part in {"node_modules", "vendor", ".git", "dist", "build"} for part in Path(name).parts):
            continue
        if path.name == ".env" or (path.name.startswith(".env.") and path.name not in {".env.example", ".env.sample", ".env.template"}):
            findings.append({"path": name, "line": None, "rule": "archivo de entorno versionado"})
        if path.stat().st_size > 2 * 1024 * 1024 or path.stat().st_size > budget:
            continue
        budget -= path.stat().st_size
        content = path.read_bytes()
        if b"\0" in content:
            continue
        scanned += 1
        for number, line in enumerate(content.decode("utf8", errors="replace").splitlines(), 1):
            for rule, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append({"path": name, "line": number, "rule": rule})
    return findings, scanned


def audit_project(args) -> int:
    root = args.directory.expanduser().resolve()
    findings, scanned = project_findings(root, include_untracked=args.include_untracked)
    result = report("sec-audit project")
    result["data"].update(directory=str(root), scanned_files=scanned, findings=findings)
    check(result, "Posibles secretos", "fail" if findings else "pass",
          f"{len(findings)} hallazgos; se muestran rutas y reglas, nunca valores")
    check(result, "Alcance", "info", "Archivos Git, patrones específicos y límite total de 64 MiB; no certifica ausencia de secretos")
    return emit(result, args)


def audit_host(args) -> int:
    result = report("sec-audit host")
    result["data"]["kernel"] = os.uname().release
    for directory in (Path.home() / ".ssh", Path.home() / ".gnupg"):
        if directory.exists():
            mode = directory.stat().st_mode & 0o777
            check(result, directory.name + " permisos", "warn" if mode & 0o077 else "pass", oct(mode))
    ssh = Path.home() / ".ssh"
    if ssh.is_dir():
        for path in ssh.iterdir():
            if path.is_file() and path.name.startswith("id_") and not path.name.endswith(".pub"):
                check(result, "Permisos " + path.name, "fail" if path.stat().st_mode & 0o077 else "pass")
    if executable("ss"):
        result["data"]["listeners"] = run([require("ss"), "-H", "-lntup"]).stdout.strip().splitlines()
    nft = executable("nft")
    if nft:
        response = run([nft, "-j", "list", "tables"], check=False)
        check(result, "Inventario de firewall", "pass" if response.returncode == 0 else "info",
              "Tablas visibles" if response.returncode == 0 else "No disponible sin permisos")
    else:
        check(result, "nftables", "info", "No instalado")
    return emit(result, args)


def dns(args) -> int:
    host = hostname(args.host)
    result = report("sec-audit dns")
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
    result["data"].update(host=host, addresses=addresses)
    check(result, "Resolución A/AAAA", "pass" if addresses else "fail")
    return emit(result, args)


def checksum(args) -> int:
    digest = hashlib.new(args.algorithm)
    with args.file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    result = report("sec-audit hash")
    result["data"].update(file=str(args.file), algorithm=args.algorithm, digest=digest.hexdigest())
    check(result, "Integridad", "pass" if not args.expect or digest.hexdigest() == args.expect.lower() else "fail")
    return emit(result, args)


def doctor(args) -> int:
    result = report("sec-audit doctor")
    for tool in ("nmap", "openssl", "git", "ip", "ss", "nft", "tailscale"):
        found = executable(tool)
        check(result, tool, "pass" if found else "info", found or "Opcional, no instalado")
    return emit(result, args)


def deps(args) -> int:
    from .web import project
    root, package, manager, _ = project(args.directory)
    if manager == "bun":
        raise ToolError("Para este gestor usa su auditoría nativa; no se infiere un lockfile npm.")
    declared = str(package.get("packageManager", ""))
    modern_yarn = manager == "yarn" and (bool(re.match(r"yarn@[2-9]", declared)) or (root / ".yarnrc.yml").exists())
    command = [manager, *(["npm"] if modern_yarn else []), "audit"] + (["--json"] if args.json else [])
    if args.dry_run:
        plan(command); return 0
    command[0] = require(manager)
    return run(command, cwd=root, timeout=args.timeout, check=False, capture=False).returncode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sec-audit", description="Auditoría de web, TLS, redes y proyectos con alcance explícito.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("http", help="Estado, redirecciones y cabeceras"); http_flags(p); p.set_defaults(fn=audit_http)
    p = sub.add_parser("tls", help="Certificado, caducidad, protocolo y cifrado")
    p.add_argument("host"); p.add_argument("--port", type=port, default=443)
    p.add_argument("--timeout", type=positive, default=10); p.add_argument("--days", type=int, default=14)
    p.add_argument("--server-name"); p.add_argument("--ca-file", type=Path)
    p.add_argument("--allow-self-signed", action="store_true"); report_flags(p); p.set_defaults(fn=audit_tls)
    p = sub.add_parser("ports", help="Escaneo TCP Nmap sobre un host o red CIDR")
    p.add_argument("target"); p.add_argument("--ports", default="22,53,80,443,445,3000,3306,5432,6379,8000,8080,8443")
    p.add_argument("--services", action="store_true"); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--rate", type=int, choices=range(1, 501), default=100, metavar="1..500")
    p.add_argument("--max-hosts", type=int, choices=range(1, 257), default=64, metavar="1..256")
    p.add_argument("--timeout", type=positive, default=60); report_flags(p); p.set_defaults(fn=audit_ports)
    p = sub.add_parser("project", help="Revisar archivos versionados sin mostrar secretos")
    p.add_argument("directory", type=Path, nargs="?", default=Path.cwd())
    p.add_argument("--include-untracked", action="store_true"); report_flags(p); p.set_defaults(fn=audit_project)
    p = sub.add_parser("host", help="Puertos locales y permisos de claves"); report_flags(p); p.set_defaults(fn=audit_host)
    p = sub.add_parser("dns", help="Resolver direcciones A/AAAA"); p.add_argument("host"); report_flags(p); p.set_defaults(fn=dns)
    p = sub.add_parser("hash", help="Calcular y verificar una suma de integridad")
    p.add_argument("file", type=Path); p.add_argument("--algorithm", choices=("sha256", "sha512"), default="sha256")
    p.add_argument("--expect"); report_flags(p); p.set_defaults(fn=checksum)
    p = sub.add_parser("doctor", help="Dependencias disponibles"); report_flags(p); p.set_defaults(fn=doctor)
    p = sub.add_parser("deps", help="Ejecutar auditoría del gestor de paquetes sin aplicar correcciones")
    p.add_argument("-C", "--directory", type=Path, default=Path.cwd()); p.add_argument("--timeout", type=positive, default=120)
    p.add_argument("--json", action="store_true"); p.add_argument("--dry-run", action="store_true"); p.set_defaults(fn=deps)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    entry(main)
