# Utilidades del día a día

Herramientas pequeñas que acompañan al escritorio Wysun. Reemplazan a `wysun tools`, que se retiró.

## Dónde van

Cada utilidad es **un paquete propio** en `apps/python/`, como cualquier app de Wysun:

```
apps/python/wysun_NOMBRE/
  __init__.py      una línea: qué hace
  __main__.py      `python3 -m wysun_NOMBRE`
  …                módulos y recursos (p. ej. static/)
```

- Se abre con `wysun NOMBRE`: una entrada en `MODULES` de `bin/wysun` (`'NOMBRE': ('app', 'wysun_NOMBRE', [])`) y una línea en su ayuda. Nada de lanzadores sueltos ni alias.
- Se instala y actualiza con el resto de Wysun (`wysun update` → `~/.local/share/wysun/app/`).
- Solo biblioteca estándar salvo motivo explícito; si un programa externo (como `ffmpeg`) falta, la utilidad sigue funcionando sin esa parte.
- Datos y caché fuera del repositorio: `~/.cache/wysun/NOMBRE`, `~/.local/share/wysun/NOMBRE`, `~/.config/wysun/NOMBRE*`.
- Añade el paquete a `PACKAGES` de `tests/test_python_layout.py` y una prueba en `tests/shell_bridge/test_dispatcher.py`.

## LANShare

```sh
wysun lanshare                              # carpeta actual, solo ver y descargar
wysun lanshare informe.pdf fotos/           # solo esos elementos, como una lista
wysun lanshare ~/Videos --subidas           # permite subir archivos y crear carpetas (solo con una carpeta)
wysun lanshare ~/Videos --clave             # genera una contraseña corta (o --clave gato123)
wysun lanshare ~/Videos --inactivo 3h       # se apaga tras 3 h sin uso (por defecto 1 h; --sin-limite)
wysun lanshare --puerto 9000                # por defecto 8000; si está ocupado usa el siguiente libre
wysun lanshare --detener PID                # lo usa la barra
```

Página en el estilo de Wysun, siempre clara, con los colores del fondo de pantalla. En el celular muestra una lista; en la computadora, una lista con panel de vista previa y un visor a pantalla completa. Tiene miniaturas y vistas previas de video al pasar el dedo o el ratón (necesitan `ffmpeg`/`ffprobe`; sin ellos no hay miniaturas), reproducción con saltos (Range, compatible con Safari/iPhone) y descarga de carpetas o de toda la lista en `.zip`. Las fuentes las sirve el propio servidor, así que funciona sin internet. Caché en `~/.cache/wysun/lanshare`; las copias de video para celular (los videos que declaran un nivel H.264 que el teléfono rechaza se reenvasan sin recodificar) ocupan como máximo 2 GB y se borran primero las vistas hace más tiempo.

- Las **subidas están apagadas** por defecto: sin `--subidas` el servidor rechaza subir y crear carpetas. Al terminar cada subida llega una notificación.
- Con `--clave`, quien abre la página escribe la contraseña una vez. Tras 5 intentos fallidos esa IP espera un minuto.
- Se **apaga solo** tras el tiempo de `--inactivo` sin uso. Una descarga o un video en curso cuentan como uso; la pantalla de contraseña, no.
- Mientras comparte, aparece un **icono en la barra**. Al pasar el ratón muestra las direcciones y la contraseña (con botón de copiar), quién está conectado, qué se descarga, cuánto falta para el apagado y «Dejar de compartir».
- Contrato con la barra: `$XDG_RUNTIME_DIR/wysun-lanshare/<pid>.json`, privado y escrito de forma atómica. Se actualiza como mucho una vez por segundo y, como mínimo, cada 10 s, y se borra al salir. Ver `apps/python/wysun_lanshare/status.py`.
- En Wysun Files: clic derecho → «Compartir en la red» (un archivo, varios o una carpeta). Pregunta si se permiten subidas (solo con una carpeta) y si se pide contraseña, y lanza `wysun lanshare RUTA… [--subidas] [--clave]` por separado.

Escucha en todas las interfaces: úsalo en redes de confianza o con `--clave`. La contraseña viaja sin cifrar (HTTP), así que en una red ajena alguien que espíe el tráfico podría verla.

Seguridad (probada en `tests/test_lanshare_server.py`):
- El servidor **nunca ejecuta** nada. Lo que se sube se guarda sin permiso de ejecución, nunca reemplaza un archivo existente y se rechaza si no cabe en el disco (deja un margen de 256 MB).
- `--subidas` no se permite en `/`, en tu carpeta personal (ni en sus carpetas superiores) ni en carpetas de `PATH`.
- Solo se sirve lo compartido: sin `..`, sin ocultos y sin enlaces que salgan de la carpeta. Una ruta con bytes nulos devuelve 404.
- HTML, SVG, XML y JS compartidos se sirven como texto plano en una caja aislada (`Content-Security-Policy: sandbox`, `nosniff`): no pueden ejecutar scripts en la página. La página tiene su propia CSP estricta y no se puede incrustar en otros sitios.
- Las escrituras (subir, crear carpeta, contraseña) exigen la cabecera `X-Wysun` y el mismo origen, así que otra página web abierta en tu navegador no puede forjarlas. Solo se responde a nombres que son este equipo (IP, `NOMBRE.local`/`.lan`…), contra DNS rebinding.
- Los nombres de archivo en las notificaciones se escapan. Una conexión que no envía nada se cierra a los 120 s.

## Wysun Cloud

```sh
wysun cloud                # interfaz a pantalla completa en la terminal
wysun cloud --estado       # una lectura para la barra (silenciosa, siempre sale con 0)
wysun cloud --terminal     # abre `wysun cloud` en una terminal nueva (lo usa la barra)
```

Vigila las VMs de Compute Engine de todos tus proyectos y las enciende, apaga o reinicia. Un **mosaico** con una columna por proyecto: cada VM encendida es una tarjeta en vivo (CPU de los últimos 2 min, RAM, disco `/`, red, tiempo encendida, proceso que más consume) y cada VM apagada, una línea. `↵` abre el **detalle** con 7 pestañas: Resumen, Procesos, Disco, Red, Servicios, Registro e Historial. Colores del fondo de pantalla (claro u oscuro en vivo), animaciones con los tokens de Wysun (`WYSUN_REDUCED_MOTION=1` las quita).

Teclas: `←↑↓→` elegir · `↵` detalle · `Esc`/`q` volver · `1`–`7` o `←→` pestaña · `x` apagar · `r` reiniciar · `s` encender · `c` SSH en una terminal · `h` 24 h / 7 días en Historial · `m` ordenar Procesos por RAM · `d` calcular `du` en Disco · `/` filtrar · `p` buscar proyectos ahora · `?` ayuda · `q` salir. Apagar y reiniciar piden confirmación; el ratón elige con un clic y abre con doble clic.

De dónde sale cada dato:
- **gcloud** (`gcloud` instalado y con sesión): proyectos, VMs, acciones (`gcloud compute instances start|stop|reset … --quiet`), operaciones, reglas de firewall y discos. Sin `gcloud` o sin sesión, una línea en rojo lo dice («gcloud no tiene sesión: ejecuta gcloud auth login») y el mosaico muestra la última lectura marcada «sin actualizar». Un proyecto que falla no oculta a los demás y conserva sus VMs conocidas.
- **SSH**, una sesión por VM encendida que manda `probe.sh` por la entrada estándar (no se instala nada en la VM) y recibe una línea por segundo. Ruta: si la VM tiene IP externa y `~/.ssh/config` tiene el alias `NOMBRE.ZONA.PROYECTO` (el que crea `gcloud compute config-ssh`), `ssh -o BatchMode=yes -o HostName=<IP actual> ALIAS`; si no, `gcloud compute ssh … --tunnel-through-iap`. Wysun nunca edita `~/.ssh/config` ni ejecuta `config-ssh`. Si la sesión cae, la tarjeta dice «reconectando…» y reintenta a los 2, 5, 15 y 30 s; si la causa es permanente, «sin SSH · motivo» (llave rechazada, IAP bloqueado, falta el alias…).
- Las pestañas Red, Servicios, Registro y Disco ejecutan al abrirse `ss -tlnp`, `systemctl --failed`, `docker ps -a`, `journalctl -p warning --since -1h` y `du`, primero con `sudo -n` (nunca pide contraseña) y, si no se puede, sin sudo, marcando «necesita permisos». La sonda de cada segundo nunca usa sudo.
- **Cloud Monitoring** (Historial): CPU de 24 h o 7 días por la API REST.

Ritmo: búsqueda completa de proyectos una vez al día (o con `p`), lista de VMs cada 30 s con la interfaz abierta y tras cada acción, sondas cada segundo; la barra lee cada 2 min. El primer cuadro sale de la caché en menos de un segundo.

Configuración opcional en `~/.config/wysun/cloud.json`: `{"projects": ["a", "b"]}` fija la lista (sin búsqueda) y `{"hidden": ["c"]}` oculta proyectos. Caché en `~/.cache/wysun/cloud` (`last.json`, `projects.json`).

Barra: mientras haya VMs encendidas aparece una nube con su número; al pasar el ratón, la lista por proyecto; un clic abre `wysun cloud`. Contrato: `$XDG_RUNTIME_DIR/wysun-cloud/state.json` (`{updated, running: [{project, name, zone}], total}`), privado (carpeta `0700`, archivo `0600`) y escrito de forma atómica por `--estado` y por la interfaz abierta; la barra ignora un estado de más de 10 min.

Credenciales: el token de Monitoring sale de `gcloud auth print-access-token` justo antes de cada consulta, viaja solo en la cabecera `Authorization` por HTTPS a `monitoring.googleapis.com` (sin seguir redirecciones) y nunca se escribe, se guarda en caché, se registra ni aparece en un error (probado en `tests/cloud/test_monitoring.py` con un token sintético). Lo que llega de las VMs se muestra sin caracteres de control.

Motor: la interfaz está hecha sobre `wysun_core.tui` (biblioteca estándar: modo crudo con restauración garantizada, lienzo de celdas con diferencias ANSI, capas con opacidad, animaciones con los tokens), reutilizable por otras utilidades de terminal.
