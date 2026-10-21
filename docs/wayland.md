# Sesión Wysun / Hyprland

Wysun se ejecuta sobre **Hyprland 0.55.x (Wayland)** con la barra y los paneles de Quickshell 0.3.x. El componente `wayland` está activo por defecto: no existe una sesión X11 alternativa en este repositorio.

Las aplicaciones de `apps/wysun/` siguen siendo Python/PySide6 y se ejecutan en Wayland nativo cuando el plugin lo permite, o sobre XWayland sin funciones X11 propias. Las funciones del escritorio no dependen de herramientas X11 (gestión de ventanas, `xrandr` ni portapapeles X11): Hyprland y sus utilidades son la única vía.

## Requisitos y paquetes

- Debian 13 (trixie) o Parrot 7 (echo), x86_64.
- El instalador usa el repositorio de la distribución y sus *backports* (`trixie-backports` o `echo-backports`). No añade ni mezcla repositorios externos.
- Versiones comprobadas: `hyprland` 0.55.x, `xdg-desktop-portal-hyprland` 1.4.x, `hyprpicker` 0.4.x. Quickshell no viene del sistema: se compila en un runtime privado (`installer/runtime_build.py`, versiones en `manifests/runtime.json`) junto con Qt 6.9.3; el plan incluye sus paquetes de compilación y la primera instalación tarda lo que dure esa compilación. El instalador rechaza el plan antes de aplicar cambios si otra serie aparece.
- `xwayland` y las bibliotecas X11 se conservan para aplicaciones heredadas. XWayland no convierte una captura X11 en una captura nativa: Recorder y Screenshot usan siempre el portal.

Puedes ver el plan sin aplicar cambios:

```sh
./instalar.sh --source "$PWD" --components desktop,wayland --plan
```

## Sesión y registro

- `bin/wysun-session` valida el entorno y arranca `start-hyprland` con `config/.config/wysun/hyprland.lua`. `--check` no inicia el compositor ni toca la sesión actual.
- `installer/session_registration.py` publica solo dos archivos: `usr/local/bin/wysun-session` y `usr/share/wayland-sessions/wysun-hyprland.desktop`. Nunca modifica la sesión predeterminada ni el gestor de acceso; mantiene un diario en `/var/lib/dotifails/wayland-session/` y admite `remove`.
- `bin/wysun-session-services` prepara D-Bus, polkit, notificaciones (`config/.config/wysun/dunstrc`) y `swayidle`/`swaylock` para el bloqueo.
- Tras cerrar sesión voluntariamente, elige **Wysun / Hyprland** en el gestor de acceso. Para retirar el registro: `python3 installer/session_registration.py remove --root /`.

## Portales y captura

- `config/.config/xdg-desktop-portal/wysun-portals.conf` usa `hyprland` para `ScreenCast` y `Screenshot`, y `gtk` para el resto.
- El instalador registra el portal `orbit-files` para el selector de archivos y lo prefiere en `portals.conf`; conserva las demás preferencias del usuario.
- Wysun Recorder muestra el diálogo de consentimiento ScreenCast/PipeWire. Wysun Screenshot sin cursor usa el portal Screenshot para congelar la región o el escritorio completo y muestra su propio marco de selección; con cursor, o al capturar una ventana/monitor concreto, usa ScreenCast. Las ventanas ocultas o minimizadas dependen del compositor y pueden no ser capturables: no se promete su captura.
- Diagnóstico sin reiniciar servicios: `~/.local/bin/wysun-session --check` y `tests/wayland_portal_probe.py`.

## Actualización y recuperación

```sh
./instalar.sh --orbit-only && ~/.local/bin/orbit reload
~/.local/bin/orbit reload              # solo recarga el residente y Quickshell
```

- `--orbit-only` (alias `--wysun-only`) no instala paquetes, no cambia atajos y no reinicia Hyprland. Actualiza el código, el lanzador y, si ya está administrado, el shell de Quickshell.
- Los atajos viven en `config/.config/wysun/hyprland.lua` y en los ajustes nativos. Se migran con respaldo y respetando asignaciones del usuario; el instalador no los sobrescribe.
- Selector de ScreenCast: `~/.config/hypr/xdph.conf` activa `allow_token_by_default` y `custom_picker_binary = ~/.local/bin/wysun-share-picker`. El Recorder deja una petición de un solo uso (`$XDG_RUNTIME_DIR/loomrec-share-request.json`, 10 s) con la pantalla elegida en su barra; el selector la responde sin ventana. Cualquier otra aplicación ve `hyprland-share-picker`. Recuperar: borrar `xdph.conf` y `systemctl --user restart xdg-desktop-portal-hyprland` (solo con autorización y sin grabaciones activas).
- Escritorios fijos: `wysun-workspaces` (llamado desde `hyprland.start` y `monitor.added`) regenera `~/.config/orbit/hypr-workspaces.lua` con el reparto guardado en Ajustes o, si no hay, el automático (1–5 / 6–9 / 10 en el portátil) y lo aplica en vivo. El automático no se guarda en `environment.json`. Para recuperar: borrar el fragmento y ejecutar `wysun-workspaces`.
- `dotifails restore ID` recupera archivos de configuración anteriores. Los respaldos de la sesión viven en `/var/lib/dotifails/wayland-session/` y `~/.local/state/dotifails/backups/`.
- Bloqueo: `wysun-lock` usa swaylock por defecto. Alternativa opt-in con `~/.config/orbit/lock.json` (`{"backend": "qml"}`) o `WYSUN_LOCK_BACKEND=qml`: pantalla de `apps/shell/lock.qml` con `WlSessionLock` y `PamContext` (servicio empaquetado `apps/shell/config/pam.d/wysun-lock`, sin tocar `/etc/pam.d`). Si falla antes de confirmar el bloqueo cae a swaylock; para volver, borrar la clave `backend`. Detalles en `apps/shell/modules/background/README.md`.

## Pruebas

- Suites generales: `python3 -m unittest discover -s tests -v`, `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`, `python3 tests/check_manifest.py`.
- Captura: `python3 apps/capture/run_tests.py` (HOME/XDG temporales y sin sesión gráfica heredada).
- Sesión y compositor: las sondas `tests/wayland_*_probe.py` usan Hyprland anidado con medios sintéticos. La sonda `tests/wayland_screenshot_route_probe.py` verifica la ruta real de Screenshot en unos 55 segundos.
- Las pruebas de medios y compositor se ejecutan en serie; un bloqueo del sandbox no demuestra un fallo del producto.
