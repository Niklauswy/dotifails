# Wysun Drive — diseño

Fecha: 2026-11-05. Estado: aprobado en conversación («haz el plan e impleméntalo»).

## Intención

El usuario tiene un Nextcloud propio en `https://cloud.wysun.store` (Nextcloud 34.0.5) y nunca ha
subido nada desde el escritorio. Quiere **subir rápido archivos y carpetas y, si lo pide, obtener al
instante el link público para compartir**, desde la terminal y desde donde tenga sentido en el
escritorio (Wysun Files, la captura de pantalla, la barra), con la misma forma y coherencia que
LANShare y Wysun Cloud. Además, otras herramientas futuras deben poder reutilizarlo: «ya existe la
utilidad de subir a la nube; intégrala».

## Metas

1. `wysun drive up RUTA… [--link]` sube archivos y carpetas a `Wysun/` en el Nextcloud. Con `--link`
   crea un link público, lo copia al portapapeles y lo imprime.
2. `wysun drive` sin argumentos abre un **selector en la terminal** hecho con `wysun_core.tui`
   (colores del wallpaper, animaciones de tokens): navegar la carpeta actual, marcar varios
   elementos, subir, ver progreso y los links; una pestaña **Recientes** con lo ya subido y sus links
   para volver a copiarlos.
3. Inicio de sesión sin escribir la contraseña: `wysun drive login` (Login Flow v2 de Nextcloud,
   por navegador) obtiene una *contraseña de aplicación* revocable.
4. Integración: Files (clic derecho → «Subir a Wysun Drive» y «Subir y copiar link»), la captura de
   pantalla («Subir y copiar link») y un icono en la barra con el progreso mientras se sube.
5. Contrato para otras herramientas: salida `--json` estable y API Python `wysun_drive.api.upload`,
   documentados en `docs/utilities.md`.

## No metas

- Sincronización (no es un cliente de escritorio de Nextcloud), descargar o navegar la nube.
- Reanudar una subida entre ejecuciones distintas (sí se reintenta cada trozo dentro de la misma).
- Varias cuentas a la vez (una cuenta; `login` otra vez la reemplaza).
- Integración con el Recorder (fase posterior).

## Anti-metas

- Que la contraseña de aplicación aparezca en una salida, aviso, error, estado de la barra o historial.
- Reemplazar en silencio un archivo remoto existente.
- Un flujo de varios pasos para la acción común: subir y copiar el link debe ser un comando o un clic.

## Restricciones (del proyecto)

- Paquete `apps/python/wysun_drive`, entrada `'drive': ('app', 'wysun_drive', [])` en `MODULES`;
  solo biblioteca estándar (urllib/http.client sobre HTTPS).
- Datos privados fuera del repo: cuenta en `~/.local/share/wysun/drive/account.json` (carpeta 0700,
  archivo 0600), historial en `~/.local/share/wysun/drive/history.json`, ajustes opcionales en
  `~/.config/wysun/drive.json` (`{"server": "...", "folder": "Wysun"}`).
- UI con tokens del tema (QML: `Tokens.*`, `Colours.*`; TUI: `Palette`), sin literales.
- Credenciales: solo HTTPS al host de la cuenta; HTTP solo para `127.0.0.1`/`localhost` (pruebas).
  Nunca se siguen redirecciones con la cabecera `Authorization`. Prueba con credenciales sintéticas.

## Cómo funciona (decidido)

### Comandos

```
wysun drive                         selector en la terminal (sin sesión: ofrece iniciarla)
wysun drive up RUTA… [opciones]     sube (por defecto a Wysun/)
    --link                          crea el link público, lo copia y lo imprime
    --clave [CLAVE]                 link con contraseña (sin valor: genera una corta)
    --caduca 7d                     el link caduca en N días
    --a CARPETA                     carpeta remota en lugar de Wysun/ (relativa a la raíz)
    --nombre NOMBRE                 nombre remoto (solo con un archivo)
    --json                          una línea JSON por elemento subido (para otras herramientas)
    --notificar                     resultado por notificación (lo usan Files y la captura)
    --sin-copiar                    no tocar el portapapeles
wysun drive login [SERVIDOR]        inicia sesión por navegador (por defecto https://cloud.wysun.store)
wysun drive logout                  olvida la contraseña de aplicación local
wysun drive recientes [--json]      lo subido y sus links
wysun drive --detener PID           cancela una subida (lo usa la barra)
wysun drive --terminal              abre `wysun drive` en una terminal nueva
```

Códigos de salida: 0 bien, 1 fallo de subida/red, 2 uso incorrecto, 3 sin sesión.

### Protocolo Nextcloud

- Login Flow v2: `POST /index.php/login/v2` → abrir `login` en el navegador (`xdg-open`) y sondear
  `poll.endpoint` con `token` cada 2 s hasta 20 min → `{server, loginName, appPassword}`.
- WebDAV `remote.php/dav/files/USUARIO/…`: `PROPFIND Depth:0` (existe), `MKCOL` (carpetas, creando
  las intermedias), `PUT` con progreso. Archivos ≥ 64 MiB: subida por trozos v2
  (`remote.php/dav/uploads/USUARIO/ID`, trozos de 16 MiB con cabecera `Destination`, `MOVE .file`);
  cada trozo se reintenta 3 veces.
- Conflictos: si el destino existe, `nombre (2).ext`, `(3)`… (también carpetas de primer nivel).
  Dentro de una carpeta nueva no hay conflictos.
- Link: OCS `POST /ocs/v2.php/apps/files_sharing/api/v1/shares` (`shareType=3`, `password`,
  `expireDate`) con `OCS-APIRequest: true`; una carpeta subida comparte la carpeta. Si el servidor
  exige contraseña o caducidad, el error lo dice en español.

### Estado para la barra

`$XDG_RUNTIME_DIR/wysun-drive/<pid>.json` (0700/0600, atómico, ≤1/s, latido cada 10 s, se borra al
salir): `{pid, started, updated, title, items: [{name, done, total}], done, total}`. La barra muestra
un icono `cloud_upload` mientras exista uno vivo (latido < 30 s); el popout lista las subidas con
barra de progreso y «Cancelar» (`wysun drive --detener PID`, que solo manda SIGTERM a un
`-m wysun_drive` del usuario). El resultado llega por notificación («Link copiado»).

### Selector TUI

Dos pestañas: **Subir** (lista de la carpeta actual: `↑↓` mover, `→`/`↵` entrar en carpeta, `←`
subir de carpeta, `espacio` marcar, `l` alternar «con link», `u` subir lo marcado o el elemento
actual, `.` ocultos) y **Recientes** (`c` copiar link, `o` abrir en el navegador, `k` crear link si no
tiene). `Tab`/`1`/`2` cambia de pestaña, `q`/`Esc` sale. Durante la subida una capa muestra el
progreso por elemento; al terminar, los links (copiados). Sin sesión: un panel que inicia el Login
Flow v2 y espera.

### Integraciones

- Files: dos entradas en el menú contextual que lanzan `wysun drive up --notificar [--link] -- RUTAS`
  por separado (Python del sistema, como LANShare).
- Captura: botón «Subir y copiar link» en la barra de acciones; guarda la PNG temporal y lanza
  `wysun drive up --link --notificar --nombre Captura_FECHA.png -- RUTA`.
- Barra: icono + popout descritos arriba.

## Decisiones del implementador (mis llamadas)

- Umbral y tamaño de trozo (64/16 MiB), reintentos (3), tiempo del login (20 min).
- Clave generada: 10 caracteres sin ambiguos.
- Historial: 200 entradas máximo.
- Sin sesión desde Files/captura: notificación «Inicia sesión con wysun drive login» y abre la
  terminal con `wysun drive login`.
