# Herramientas del escritorio

Un único comando: `orbit-tools`. Panel gráfico: **Super + Shift + O**, `orbit tools` o `orbit-tools gui`.

```sh
./instalar.sh --scripts-only
orbit-tools --help
```

| Carpeta | Contenido |
| --- | --- |
| `bin/orbit-tools` | Único lanzador de desarrollo |
| `apps/tools/` | CLI y motor compartido |
| `apps/orbit/tools_window.py` | Panel gráfico |
| `docs/tools.md` | Esta guía |
| `~/scripts/` | Lanzador y guía instalados |
| `~/.local/share/orbit/tools/` | Motor instalado |
| `~/.config/orbit/tools.json` | Lista privada de proyectos |
| `~/.config/orbit/resets/` | Recordatorios privados |
| `~/.local/share/orbit/transfers/inbox/` | Archivos recibidos |

La instalación completa también incluye estas herramientas. La migración respalda los scripts anteriores, retira las duplicaciones administradas y mueve cuentas y subidas fuera de `~/scripts`. Los aliases antiguos se conservan en `~/.local/bin` para los comandos de terminal. Las rutas absolutas antiguas dentro de `~/scripts` se sustituyen por `~/scripts/orbit-tools <grupo>`. `dotifails restore ID` recupera una migración; conserva también las modificaciones posteriores en el respaldo. Los datos privados nunca se añaden al repositorio. No hay dependencias Python externas para la CLI.

## Panel gráfico

- **Proyectos:** añade carpetas, recuerda tu lista, abre el editor y ejecuta las tareas disponibles en una terminal. Comprueba el proyecto y los nombres de variables sin publicar valores.
- **Diagnósticos:** HTTP, TLS, puertos TCP, sistema local y secretos del proyecto seleccionado. Revisión explícita, cancelación y resultados en la misma ventana.
- **Archivos:** inicia y detiene un servidor local, abre el navegador y recibe archivos en una bandeja separada. Al cerrar el panel o recargar Wysun se detienen sus procesos. LAN pide el código en una terminal.
- **Recordatorios:** consulta tus tiempos guardados y abre la edición en terminal.

La nube y la VPN permanecen en la CLI. No se ejecutan automáticamente al abrir el panel.

## Desarrollo web

```sh
orbit-tools dev doctor -C ./proyecto
orbit-tools dev dev -C ./proyecto --port 3000 --host 127.0.0.1 --dry-run
orbit-tools dev dev -C ./proyecto -- --turbopack
orbit-tools dev build -C ./proyecto
orbit-tools dev test -C ./proyecto
orbit-tools dev lint -C ./proyecto
orbit-tools dev typecheck -C ./proyecto
orbit-tools dev env -C ./proyecto --json
orbit-tools dev ports --port 3000
orbit-tools dev stop --port 3000 --dry-run
orbit-tools dev init ./nuevo-sitio
orbit-tools dev serve -C ./nuevo-sitio --port 8080
orbit-tools dev check http://127.0.0.1:8080 --expect 200
```

Detecta npm, pnpm, Yarn y Bun mediante `packageManager` y lockfiles; rechaza gestores incompatibles. Las tareas ejecutan los scripts existentes, sin instalar dependencias. Los argumentos adicionales van después de `--`. Las opciones `--port` y `--host` se adaptan a Next, Vite, Astro o Nuxt; Vite usa un puerto estricto. `env` compara nombres, nunca valores. `stop` verifica propietario e identidad del proceso y envía SIGTERM mediante pidfd; no mata procesos ajenos.

## Auditoría web, redes, CTF y Linux

```sh
orbit-tools audit doctor
orbit-tools audit http https://tu-dominio.example --json
orbit-tools audit tls tu-dominio.example --days 30
orbit-tools audit ports 127.0.0.1 --ports 22,80,443 --dry-run
orbit-tools audit ports 10.10.10.0/28 --ports 1-1024 --services --output ./red.json
orbit-tools audit project ./proyecto --include-untracked --output ./proyecto.json
orbit-tools audit deps -C ./proyecto --dry-run
orbit-tools audit host
orbit-tools audit dns tu-dominio.example
orbit-tools audit hash ./archivo.iso --algorithm sha256 --expect SUMA
```

`http` revisa estado, redirecciones, cabeceras y atributos de cookies; `tls` valida el certificado y hostname, protocolo, cifrado y caducidad. `--allow-self-signed` es para laboratorios y registra que la validación se desactivó. Nmap usa conexiones TCP, alcance explícito, límite de hosts y velocidad; el análisis de servicios es optativo y no ejecuta NSE. Úsalo sobre tus equipos, laboratorios o auditorías autorizadas.

El análisis de secretos muestra solamente ruta, línea y regla. Examina archivos de Git, omite binarios, enlaces y carpetas de dependencias, con límites de 2 MiB por archivo y 64 MiB total. Son comprobaciones acotadas, no una certificación de seguridad. `deps` ejecuta la auditoría nativa del gestor, sin aplicar correcciones; puede consultar su registro y conserva su código de salida.

Los informes nuevos tienen permisos 600 y no sobrescriben otros informes salvo `--force-output`. Los diagnósticos devuelven 0 si no hay fallos, 1 si hay hallazgos y 2 ante errores operativos; `--strict` también convierte advertencias en código 1. Las tareas externas conservan su código de salida. Ctrl+C devuelve 130, salvo el servidor de archivos, que cierra ordenadamente.

## Compartir archivos

```sh
orbit-tools share -C ./public --port 8000
orbit-tools share -C ./public --uploads --max-mb 32
orbit-tools share -C ./public --lan --ask-code --uploads
orbit-tools share -C ./public --lan --key-file ./acceso.txt --cert ./cert.pem --key ./key.pem
```

Por defecto escucha solamente en localhost, sin subidas. En LAN pide un código (usuario `orbit`); los procesos no interactivos requieren `--key-file` con permisos 600 o `--public` explícito. HTTP no cifra archivos ni credenciales: para transferencias confidenciales usa `--cert` y `--key` o una red VPN de confianza. El código no aparece en los logs. Se bloquean archivos ocultos, rutas fuera de la carpeta y enlaces que salen de ella. La página neutra permite arrastrar archivos, buscarlos, revisar la cola, cancelar y reintentar envíos; muestra progreso individual y respeta movimiento reducido. Las subidas se reciben por streaming, con tamaño y conexiones limitadas, permisos 600 y nombres únicos sin reemplazar archivos.

`web-dev serve` permite renderizar HTML del proyecto; `file-share` descarga los archivos como adjuntos. Son herramientas locales, no servidores para publicar en producción. `zzzz.py` conserva el nombre anterior y acepta el puerto posicional; ahora las subidas se habilitan explícitamente.

## Google Cloud

```sh
orbit-tools cloud                         # selector fzf en una terminal interactiva
orbit-tools cloud list --project mi-proyecto --json
orbit-tools cloud --account cuenta@example.test list --all-projects
orbit-tools cloud stop --vm proyecto/zona/nombre --dry-run
orbit-tools cloud start --vm proyecto/zona/uno --vm proyecto/zona/dos
orbit-tools cloud ssh --vm proyecto/zona/nombre
orbit-tools cloud upload ./archivo.txt /tmp/archivo.txt --vm proyecto/zona/nombre
orbit-tools cloud download ./archivo-nuevo.txt /tmp/archivo.txt --vm proyecto/zona/nombre
orbit-tools cloud run ./provisionar.sh --directory /home/usuario/app --vm proyecto/zona/nombre --dry-run
```

Usa JSON de gcloud y selectores `PROJECT/ZONE/NAME`, sin cambiar la cuenta o proyecto global. Las consultas y operaciones paralelas tienen un máximo de trabajadores y tiempos límite. Cada VM tiene su resultado; los fallos parciales producen código 1. Reset y delete piden confirmación exacta o `--yes`. `--dry-run` de una operación no consulta ni modifica VMs. SSH abre una sesión a la vez. Descargas no reemplazan un destino existente. Las rutas remotas no admiten metacaracteres.

El antiguo SETUP automático que descargaba y ejecutaba instaladores remotos se sustituye por `run`: prepara y revisa un script local, inspecciona su plan y ejecútalo sobre VMs concretas. `gvm.sh` sigue disponible como alias. Requiere gcloud autenticado y permisos sobre los proyectos; fzf solamente para el selector.

## Tailscale

```sh
orbit-tools vpn plan
orbit-tools vpn on 100.64.0.10 --dry-run
sudo ~/scripts/orbit-tools vpn on 100.64.0.10
sudo ~/scripts/orbit-tools vpn status
sudo ~/scripts/orbit-tools vpn off
```

Usa una tabla propia de nftables para IPv4 e IPv6, permite Tailscale y su transporte marcado, loopback y tráfico mínimo de configuración de red. No permite acceso LAN directo mientras el bloqueo está activo. Guarda las preferencias previas antes de modificar nada y las restaura antes de retirar el bloqueo. Si la restauración falla, conserva protección y estado para recuperación. Solo elimina su propia tabla; no cambia políticas globales ni vacía el firewall.

El estado privilegiado está en `/var/lib/dotifails/tailscale-killswitch/state.json`. Si detecta reglas de la implementación antigua, se niega a mezclar ambas. Esta herramienta no intenta adivinar ni restablecer las políticas IPv6 que dejó el script anterior. Los aliases `scrip.sh` y `tailscale-killswitch.sh` usan el mismo motor. La activación real necesita privilegios; la instalación no activa la VPN ni modifica el firewall.

## Contadores personales

```sh
orbit-tools resets
orbit-tools resets --json list
orbit-tools resets --service codex --watch 10 list
orbit-tools resets add laboratorio codex '2027-01-01T10:00:00-08:00'
orbit-tools resets paste --service codex
orbit-tools resets edit
orbit-tools resets --config ./cuentas-lab.json list
```

Conserva add/rm/edit/init/paste y resets múltiples. Los datos anteriores de `~/scripts/.rezets/accounts.json` se migran durante la instalación o al primer uso a `$XDG_CONFIG_HOME/orbit/resets/accounts.json` (por defecto `~/.config`), con el original respaldado durante la reorganización. Guardados atómicos privados, copia `.json.bak`, rechazo de nombres duplicados y restauración si una edición es inválida. `--config` usa un archivo independiente sin migración. Estos tiempos son recordatorios que introduces tú; no consultan ni predicen cuotas de proveedores.

## Verificación

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/check_manifest.py
```

Las pruebas de las herramientas usan directorios temporales, un servidor localhost y proveedores simulados. No activan el firewall real ni ejecutan operaciones en Google Cloud.

Referencias: [Tailscale exit nodes](https://tailscale.com/docs/features/exit-nodes), [marcas del transporte Tailscale](https://github.com/tailscale/tailscale/blob/main/tsconst/linuxfw.go), [gcloud scripting](https://docs.cloud.google.com/sdk/docs/scripting-gcloud), [Nmap TCP connect](https://nmap.org/book/man-port-scanning-techniques.html), [Yarn audit](https://yarnpkg.com/cli/npm/audit).
