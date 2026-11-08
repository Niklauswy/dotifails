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

### Utilidades de terminal: la misma base

Las utilidades con interfaz de terminal (Wysun Cloud, Wysun Drive y las que vengan) se hacen sobre `wysun_core.tui` y se ven y se manejan igual:

- La app es **transparente** (`transparent = True` en la subclase de `App`): las celdas sin color propio no pintan fondo y se ve el Ghostty desenfocado. El Ghostty de Wysun usa `background-opacity-cells = true`, así que los chips, la fila elegida y los paneles con color también dejan ver el fondo.
- Las piezas comunes salen de `wysun_core.tui.kit`: `header` (chip con icono Nerd Font, pestañas o ruta, y estado con punto de color a la derecha), `crumbs`, `footer` (teclas), `chip`, `Toast` (avisos en la fila del pie con fundido), `HelpLayer` (la ayuda de `?`, se cierra con cualquier tecla), `pixels` (imágenes en medios bloques `▀`) y `GLYPH`. Colores solo de la paleta (`kit.Painter`); movimiento con los tokens y sin animaciones con `WYSUN_REDUCED_MOTION=1`.
- Convenciones de teclas: `?` ayuda, `/` filtrar, `Tab`/números para pestañas, `Esc` volver o cancelar, `q` salir.
- `tests/tui/test_kit.py` comprueba que cada utilidad es transparente y usa `kit.Toast` y `kit.HelpLayer`; añade ahí la nueva.

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

Vigila las VMs de Compute Engine de todos tus proyectos y las enciende, apaga o reinicia. Transparente sobre el Ghostty y con la base común de las utilidades de terminal (cabecera, avisos y ayuda de `wysun_core.tui.kit`). Un **mosaico** con una columna por proyecto: cada VM encendida es una tarjeta en vivo (CPU de los últimos 2 min, RAM, disco `/`, red, tiempo encendida, proceso que más consume) y cada VM apagada, una línea. `↵` abre el **detalle** con 8 pestañas: Resumen, Procesos, Disco, Red, Servicios, Registro, Historial y Apagado. Colores del fondo de pantalla (claro u oscuro en vivo), animaciones con los tokens de Wysun (`WYSUN_REDUCED_MOTION=1` las quita).

Teclas: `←↑↓→` elegir · `↵` detalle · `Esc`/`q` volver · `1`–`8` o `←→` pestaña · `x` apagar · `r` reiniciar · `s` encender · `a` apagado automático · `p` posponer 1 h (pestaña Apagado) · `c` SSH en una terminal · `h` 24 h / 7 días en Historial · `m` ordenar Procesos por RAM · `d` calcular `du` en Disco · `/` filtrar · `p` buscar proyectos ahora · `?` ayuda · `q` salir. Apagar y reiniciar piden confirmación; el ratón elige con un clic y abre con doble clic.

De dónde sale cada dato:
- **gcloud** (`gcloud` instalado y con sesión): proyectos, VMs, acciones (`gcloud compute instances start|stop|reset … --quiet`), operaciones, reglas de firewall y discos. Sin `gcloud` o sin sesión, una línea en rojo lo dice («gcloud no tiene sesión: ejecuta gcloud auth login») y el mosaico muestra la última lectura marcada «sin actualizar». Un proyecto que falla no oculta a los demás y conserva sus VMs conocidas.
- **SSH**, una sesión por VM encendida que manda `probe.sh` por la entrada estándar (no se instala nada en la VM) y recibe una línea por segundo. Ruta: si la VM tiene IP externa y `~/.ssh/config` tiene el alias `NOMBRE.ZONA.PROYECTO` (el que crea `gcloud compute config-ssh`), `ssh -o BatchMode=yes -o HostName=<IP actual> ALIAS`; si no, `gcloud compute ssh … --tunnel-through-iap`. Wysun nunca edita `~/.ssh/config` ni ejecuta `config-ssh`. Si la sesión cae, la tarjeta dice «reconectando…» y reintenta a los 2, 5, 15 y 30 s; si la causa es permanente, «sin SSH · motivo» (llave rechazada, IAP bloqueado, falta el alias…).
- Las pestañas Red, Servicios, Registro y Disco ejecutan al abrirse `ss -tlnp`, `systemctl --failed`, `docker ps -a`, `journalctl -p warning --since -1h` y `du`, primero con `sudo -n` (nunca pide contraseña) y, si no se puede, sin sudo, marcando «necesita permisos». La sonda de cada segundo nunca usa sudo.
- **Cloud Monitoring** (Historial): CPU de 24 h o 7 días por la API REST.

### Apagado automático

`a` (en el mosaico o en el detalle) abre **Apagado automático** para la VM elegida. Cada regla se activa con `espacio` y se ajusta con `←→`; se pueden combinar y gana la que llegue antes:

- **Horario fijo**: a una hora (`←→` ±15 min, `RePág`/`AvPág` ±1 h) los días elegidos (`←→` todos / lunes a viernes / fines de semana; `1`–`7` cambia un día). La hora es la de este equipo (se guarda con su zona horaria). Cuenta desde que se guarda y desde que la VM arrancó: encenderla después de la hora no la apaga en el acto.
- **Tiempo máximo**: N horas después de encenderse (o de guardar la regla, si es más tarde).
- **Sin actividad**: N minutos seguidos sin uso. Es uso: CPU por encima del umbral, una sesión SSH interactiva (opcional; la sonda de Wysun Cloud no cuenta) o un proceso de la lista (`claude`, `codex`, `opencode`, editable en el archivo de la VM).
- **Una vez**: `shutdown -h +N` (o el que ya hubiera). Quitarlo hace `shutdown -c`.
- **Aplicar a**: esta VM, todas las encendidas o una lista para marcar. Solo se configuran VMs encendidas.

El panel muestra cuándo será el próximo apagado con esos valores. Las tarjetas del mosaico lo enseñan en su borde inferior (en color cuando faltan 15 min o menos) y la pestaña **Apagado** detalla las reglas, si ahora está en uso y por qué, y desde cuándo está quieta; `p` pospone 1 h el próximo apagado. Cinco minutos antes, quien tenga sesión en la VM recibe un aviso (`wall`).

Cómo funciona: todo corre en la VM, sin cambios de IAM. Al guardar, Wysun Cloud manda por SSH un script a `sudo -n sh -s` (nunca pide contraseña: si la VM la exige, el aviso lo dice) que instala `/usr/local/libexec/wysun-autostop`, `wysun-autostop.service` y `wysun-autostop.timer` (cada minuto) y escribe las reglas en `/etc/wysun-autostop.conf`, validadas antes porque las lee root. El estado queda en `/var/lib/wysun-autostop/state`, que la sonda lee cada segundo (campo `auto=`). Quitar todas las reglas desinstala todo eso. Pruebas: `tests/cloud/test_autostop.py` ejecuta el script real con reloj, CPU, sesiones y procesos falsos.

Ritmo: búsqueda completa de proyectos una vez al día (o con `p`), lista de VMs cada 30 s con la interfaz abierta y tras cada acción, sondas cada segundo; la barra lee cada 2 min. El primer cuadro sale de la caché en menos de un segundo.

Configuración opcional en `~/.config/wysun/cloud.json`: `{"projects": ["a", "b"]}` fija la lista (sin búsqueda) y `{"hidden": ["c"]}` oculta proyectos. Caché en `~/.cache/wysun/cloud` (`last.json`, `projects.json`).

Barra: mientras haya VMs encendidas aparece una nube con su número; al pasar el ratón, la lista por proyecto; un clic abre `wysun cloud`. Contrato: `$XDG_RUNTIME_DIR/wysun-cloud/state.json` (`{updated, running: [{project, name, zone}], total}`), privado (carpeta `0700`, archivo `0600`) y escrito de forma atómica por `--estado` y por la interfaz abierta; la barra ignora un estado de más de 10 min.

Credenciales: el token de Monitoring sale de `gcloud auth print-access-token` justo antes de cada consulta, viaja solo en la cabecera `Authorization` por HTTPS a `monitoring.googleapis.com` (sin seguir redirecciones) y nunca se escribe, se guarda en caché, se registra ni aparece en un error (probado en `tests/cloud/test_monitoring.py` con un token sintético). Lo que llega de las VMs se muestra sin caracteres de control.

Motor: la interfaz está hecha sobre `wysun_core.tui` (biblioteca estándar: modo crudo con restauración garantizada, lienzo de celdas con diferencias ANSI, capas con opacidad, animaciones con los tokens), reutilizable por otras utilidades de terminal.

## Wysun Drive

```sh
wysun drive                                  # selector en la terminal: marca, sube, Recientes con sus links
wysun drive up informe.pdf fotos/            # sube a Wysun/ en tu Nextcloud
wysun drive up informe.pdf --link            # además crea el link público, lo copia y lo imprime
wysun drive up video.mp4 --clave --caduca 7d # link con contraseña generada que caduca en 7 días
wysun drive up captura.png --a Trabajo --nombre portada.png
wysun drive login [SERVIDOR]                 # inicia sesión desde el navegador
wysun drive login --manual                   # con una contraseña de aplicación creada en Nextcloud
wysun drive logout                           # cierra la sesión y revoca la contraseña de aplicación
wysun drive ajustes --servidor nube.ejemplo.com --carpeta Compartido
wysun drive estado [--json] | recientes [--json]
```

Sube archivos y carpetas a un Nextcloud (por defecto `https://cloud.wysun.store`, cualquier otro desde **Ajustes › Wysun Drive**, `wysun drive ajustes --servidor` o la tecla `s` del panel de inicio de sesión). Una sesión solo vale para su servidor: al cambiarlo hay que volver a iniciar sesión.

- **Inicio de sesión** con el Login Flow v2 de Nextcloud: se abre el navegador, autorizas y Wysun recibe una *contraseña de aplicación* (revocable desde la seguridad de tu cuenta de Nextcloud o con `logout`). Si el navegador falla (por ejemplo «State token does not match») o tu cuenta usa 2FA o SSO, crea una contraseña de aplicación en Nextcloud (Ajustes personales › Seguridad) y úsala con `wysun drive login --manual` o la tecla `p` del panel de sesión; se comprueba contra el servidor antes de guardarla y nunca se muestra. Se guarda en `~/.local/share/wysun/drive/account.json` (carpeta `0700`, archivo `0600`), nunca en el repositorio.
- **Subidas** por WebDAV; los archivos de 64 MB o más van en trozos de 16 MB (subida por trozos v2) y cada trozo se reintenta 3 veces. Un nombre que ya existe en la nube se sube como `nombre (2).ext`: nunca se reemplaza nada. Dentro de una carpeta se omiten enlaces simbólicos y archivos especiales (se avisa).
- **Links**: públicos y de solo lectura (OCS `shareType=3`), opcionalmente con contraseña y caducidad. Se copian con `wl-copy` salvo `--sin-copiar`. Si el servidor exige contraseña, el error lo dice y la subida queda hecha.
- **Selector** (`wysun drive` sin argumentos; `wysun_core.tui` con fondo transparente sobre el Ghostty, colores del wallpaper, `WYSUN_REDUCED_MOTION=1` quita animaciones). Dos paneles: **Archivos** (iconos por tipo, tamaño, fecha, resumen de la carpeta) y **Detalle** (vista previa de imágenes y videos en medios bloques `▀` con `ffmpeg`, primeras líneas de texto o resumen de carpeta; a dónde irá y si ya existe en la nube). Arriba, migas de pan y espacio libre en tu Nextcloud; abajo, la bandeja con lo marcado y los chips. Teclas: `↑↓` mover, `→`/`↵` entrar, `←` subir de carpeta, `espacio` marcar, `a` todo, `u` subir, `l` link, `p` contraseña generada, `d` caducidad (no · 1 · 7 · 30 días), `/` filtrar, `.` ocultos, `?` ayuda, `Tab`/`1`/`2` pestañas. Mientras sube, el Detalle muestra barras, total, velocidad y tiempo restante: `Esc` cancela y `b` o `q` cierran el selector dejando la subida en segundo plano (barra y notificación al terminar). **Recientes** agrupa por Hoy / Ayer / Esta semana / Antes: `c` copia el link (o lo crea), `o` lo abre, `k` lo quita (el archivo sigue en la nube), `n` crea uno nuevo con los chips. Pegar rutas o arrastrar archivos a la terminal los marca. Debajo de 100 columnas solo se ve un panel. El Ghostty de Wysun usa `background-opacity-cells = true` para que también los paneles y chips dejen ver el fondo.
- **Escritorio**: Files → clic derecho → «Subir a Wysun Drive» o «Subir y copiar link»; la captura de pantalla → «Upload & copy link» (`U`); el lanzador y Ajustes › Wysun Drive. Mientras sube aparece un icono en la barra con el progreso y «Cancelar»; el resultado llega como notificación («Link copiado»). Sin sesión, la notificación lo dice y se abre `wysun drive` en una terminal para iniciarla.
- El selector sube con un `wysun drive up … --resultado ARCHIVO --origen terminal` hijo en su propia sesión y lo sigue por el archivo de estado de la barra; si se cierra, crea `ARCHIVO.notificar` y el hijo avisa al terminar. Files y la captura pasan `--origen files|captura`, que Recientes muestra.
- Ajustes en `~/.config/wysun/drive.json` (`{"server": "https://…", "folder": "Wysun"}`); historial (200 entradas) en `~/.local/share/wysun/drive/history.json`.
- Contrato con la barra: `$XDG_RUNTIME_DIR/wysun-drive/<pid>.json` (`{pid, started, updated, title, items: [{name, done, total}], done, total}`), privado, atómico, latido cada 10 s; vivo si tiene menos de 30 s. `wysun drive --detener PID` solo detiene un `-m wysun_drive` del usuario.

Credenciales: la contraseña de aplicación viaja solo en la cabecera `Authorization` por HTTPS al servidor de la cuenta (HTTP solo a `127.0.0.1`/`localhost`, para pruebas), sin seguir redirecciones, y nunca aparece en salidas, errores, notificaciones, el estado de la barra ni el historial (probado en `tests/drive/` con una contraseña sintética y un Nextcloud falso).

### Para otras herramientas

Cualquier cosa de Wysun que necesite subir a la nube y obtener un link usa Wysun Drive en vez de hablar con Nextcloud por su cuenta:

```sh
wysun drive up --link --json -- RUTA…
# una línea JSON por ruta: {"ok": true, "name": "…", "remote": "Wysun/…", "url": "https://…/s/…",
#                           "password": null, "size": 123, "is_dir": false, "error": null, "link_error": null}
# salida: 0 todo bien · 1 algo falló · 2 uso incorrecto · 3 sin sesión (wysun drive login)
```

Añade `--notificar` para que el usuario vea el resultado y `--sin-copiar` si no quieres tocar el portapapeles. Así la subida aparece en la barra y se puede cancelar. Desde Python dentro de Wysun también vale `wysun_drive.api.upload(paths, link=True)` (devuelve `Result` con `url`; lanza `AuthError` con `code == 3` sin sesión).
