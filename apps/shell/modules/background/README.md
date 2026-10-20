# Fondo y reloj Wysun

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun. Referencia:
`507d66285e9d9fde9330adc64159cfdebb28c19a`; mapa en `THIRD_PARTY.md`.

`Desktop.qml` instancia un fondo pasivo por salida mediante `Variants`.
`Wallpaper.qml` conserva la selección existente `environment.json` →
`wallpaper.default`, `wallpaper.mode`, `wallpaper.monitors[nombre].path/mode`.
Solo carga imágenes locales. Si faltan o son inválidas, muestra el canvas del
tema. No escribe preferencias ni `scheme.json`.

El reloj está desactivado por defecto. Se activa explícitamente mediante:

```json
{"wallpaper":{"clock":{"enabled":true,"position":"top-left"},
 "monitors":{"DP-1":{"clock":{"enabled":false}}}}}
```

Cada salida hereda `wallpaper.clock`; su entrada `clock` permite sustituir
`enabled` y/o `position`. Posiciones: `top|middle|bottom` + `left|center|right`.
Un valor inválido vuelve a `top-left`. El fullscreen solo desactiva el reloj
local, no el fondo ni el reloj de otra salida. Al desconectar la salida se
destruye su delegado; no hay caché global de nombres de monitor. `SystemClock`
solo existe con el reloj visible y usa hora real a precisión de minutos para
reflejar wake/cambio horario. No hay animaciones idle ni transiciones (también
respeta movimiento reducido sin crear excepciones).

La fuente y las dimensiones proceden de `Appearance`; Rubik se carga offline
por el shell. La placa sólida conserva contraste en fondos claros/oscuros.
No requiere nuevos símbolos ni amplía el subconjunto Material Symbols.

## Bloqueo

`bin/wysun-lock` conserva **swaylock** como bloqueo predeterminado: su config
implícita se omite, no muestra fondo, portada, perfil, notificaciones ni
metadatos, y solo se suspende después de adquirir el bloqueo. Los colores y la
geometría se toman de los tokens cuando el panel Qt lo solicita; invocaciones
directas conservan el canvas opaco de recuperación.

Alternativa opt-in (`modules/lock/`, `lock.qml`), desactivada por defecto. Se
activa con `~/.config/orbit/lock.json`:

```json
{"backend": "qml", "media": false}
```

o con `WYSUN_LOCK_BACKEND=qml` (la variable manda sobre el archivo). Cualquier
valor desconocido conserva swaylock. Usa `WlSessionLock` (ext-session-lock-v1)
de Quickshell 0.3.0: si el proceso o la shell mueren con la sesión bloqueada,
el compositor mantiene la sesión bloqueada. La autenticación usa `PamContext`
con el servicio empaquetado `config/pam.d/wysun-lock`, que solo hace
`auth include /etc/pam.d/login`; no se modifica `/etc/pam.d` ni el login. Un
único camino desbloquea: éxito de PAM. Sin IPC, sin captura de pantalla, sin
cava. El mapa visual (reloj, fecha, campo de contraseña, mensajes de estado,
tarjeta multimedia) y los componentes derivados están en `THIRD_PARTY.md`.

`wysun-lock` espera hasta 30 s (`WYSUN_LOCK_WAIT`, 1–60) el marcador de
disponibilidad que el cliente publica solo cuando el compositor confirmó el
bloqueo. Si el cliente falla antes de confirmar, usa swaylock; si sigue vivo
sin confirmar, no lanza un segundo bloqueador encima ni suspende.
`media: true` muestra título/artista y controles del reproductor MPRIS activo
en la pantalla bloqueada; es opt-in porque expone metadatos.

Recuperación: si el cliente muere con la sesión bloqueada, Hyprland deja la
pantalla de aviso. Hyprland solo acepta un cliente de bloqueo nuevo si
`misc:allow_session_lock_restore` está activo (esta configuración no lo cambia;
es un ajuste del compositor, no verificado aquí). Desde otra TTY, con
`HYPRLAND_INSTANCE_SIGNATURE` de la sesión, se puede activar en caliente con
`hyprctl keyword misc:allow_session_lock_restore 1` y volver a ejecutar
`wysun-lock`. La contraseña de la cuenta desbloquea. Este mismo límite ya existe
con swaylock.

## Verificación aislada

```sh
python3 -m unittest apps/shell/tests/test_phase5_background.py apps/shell/tests/test_phase5_lock.py -v
```

Usan imágenes sintéticas, un servicio PAM temporal con secreto sintético,
procesos fixture (swaylock/quickshell/systemctl) y HOME/XDG temporales con
`QT_QPA_PLATFORM=offscreen`. No adquieren un bloqueo físico ni ejecutan un
compositor. **No validado aquí:** el bloqueo real con `ext-session-lock-v1`, el
desbloqueo con la contraseña real y la recuperación tras matar el cliente; deben
probarse en una sesión de prueba autorizada.
