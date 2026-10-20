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

El bloqueo continúa siendo swaylock, sin superficies Qt por encima. Su config
implícita se omite para garantizar privacidad por defecto. No se leen fondo,
portada, perfil, notificaciones ni metadatos. Los colores/geometría se toman de
los tokens cuando el panel Qt lo solicita; invocaciones directas conservan el
canvas opaco de recuperación. Solo se suspende después de adquisición exitosa.
El porte completo del diseño de lock Caelestia está pendiente: swaylock estándar
no tiene reloj, avatar, campo personalizado ni tarjetas multimedia.

Verificación aislada:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s apps/shell/modules/background -p 'test_*.py' -v
```

Estas pruebas usan imágenes sintéticas, procesos fixture y HOME/XDG temporales.
No prueban un bloqueo físico ni ejecutan un compositor/Quickshell de sesión.
