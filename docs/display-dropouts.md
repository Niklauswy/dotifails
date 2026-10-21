# Apagones intermitentes de monitores (DP-1 / DP-2)

Diagnóstico del 2026-10-21 (portátil con Intel UHD 620; eDP-1 BOE 60 Hz, DP-1 LG ULTRAGEAR 1920x1080@144, DP-2 Philips PHL 271E1 60 Hz).

## Evidencia

- `hyprland.log` registra `Got a hotplug event` del kernel (udev `change` de `card0`) seguido de `Connector DP-1 disconnected` y `Connector DP-2 disconnected`; después `Disabling output`. Es decir, el **kernel reporta HPD bajo** en los conectores DP: Hyprland solo reacciona.
- DP-1 y DP-2 caen juntos (mismo evento), y en el primer caso los teclados/ratones USB (hub USB-C con clase *Billboard* en `lsusb -t`) se reenumeran justo antes. Apunta a un dock/cable USB-C DP-alt que renegocia, no a un monitor concreto.
- Al volver, DP-2 puede dar `failed to parse edid` (enlace inestable en la reconexión). DP-1 reconecta con `1920x1080@144` sin error.
- Ningún proceso de Wysun reaplica monitores: no hay `hyprctl keyword monitor`, ni `dpms`, ni recargas periódicas. `swayidle` solo ejecuta `wysun-lock` (600 s) y no toca DPMS. `hyprctl reload` solo ocurre con `Super+Escape`. VRR está desactivado (el CRTC no es capaz) y el formato es XRGB8888 (sin 10 bits).
- `Cannot commit when a page-flip is awaiting` aparece en el arranque y durante los cambios de modo; es ruido del backend, no la causa.

## Conclusión

Causa de hardware/enlace (HPD/alt-mode del dock o cable USB-C, ancho de banda de 144 Hz sobre 2 carriles compartidos con USB). X11 con BSPWM no lo evitaba por software: simplemente no se veía igual porque no destruía/recolocaba salidas. Wysun ya conserva escritorios y ventanas al desconectar (commit 8a72347b).

## Ajuste de software recomendado (reversible)

Si los apagones continúan, bajar DP-1 a 120 Hz reduce el ancho de banda del enlace. En `~/.config/orbit/hypr-monitors.lua` (se regenera desde Ajustes > Pantallas) cambiar el modo de DP-1 a `1920x1080@120.00`, o elegirlo en Ajustes. Para volver: restaurar `@144.00`. No se aplica por defecto porque no está demostrado que mejore.

## Captura del próximo apagón

Registrador ligero (eventos `monitor*` del socket2 de Hyprland más cambios de `/sys/class/drm/*/status`, con marca de tiempo):

```sh
socat -u "UNIX-CONNECT:$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock" - | while read -r l; do echo "$(date '+%F %T.%3N') $l"; done
```

Compararlo con `journalctl -k` (requiere pertenecer al grupo `systemd-journal`/`adm`) en busca de `[drm] *ERROR* ... link training`, `HPD` o `Billboard`. Si DP-1 y DP-2 caen a la vez, probar otro cable/puerto USB-C o conectar DP-1 directo al puerto DisplayPort/HDMI del equipo.
