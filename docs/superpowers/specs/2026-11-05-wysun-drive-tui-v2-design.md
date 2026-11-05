# Wysun Drive · selector v2 (opción B) — diseño

Fecha: 2026-11-05. Estado: aprobado en conversación («me gusta todo», las 5 ideas marcadas en el
mockup renderizado con el motor real: `.superpowers/brainstorm/…/drive-b-v3.html`).

## Intención

El selector de `wysun drive` funciona pero es plano y opaco. El usuario quiere que se integre con su
escritorio (fondo transparente sobre el Ghostty desenfocado) y que se sienta como una herramienta
completa: dos paneles, vista previa, progreso en el propio panel, chips de opciones y Recientes útil.

## Metas (todo lo del mockup)

1. **Fondo transparente**: las celdas sin color propio no pintan fondo; se ve el Ghostty (0.6 + blur).
   Opción del motor (`App(transparent=True)`), reutilizable por Wysun Cloud.
2. **Celdas translúcidas**: `background-opacity-cells = true` en el Ghostty de Wysun
   (`config/.config/ghostty/config`), también para el resto de apps (aceptado por el usuario).
3. **Dos paneles**: Archivos (izquierda, borde grueso `primary` cuando tiene el foco) con icono Nerd Font
   por tipo, tamaño, fecha relativa y resumen en el borde inferior; Detalle (derecha).
4. **Cabecera**: chip, pestañas, punto de estado + `usuario · host`; fila de migas de pan y, a la
   derecha, espacio libre en la nube (WebDAV `quota-available-bytes`/`quota-used-bytes`).
5. **Detalle**: nombre, tipo legible, vista previa (imágenes y primer fotograma de video en medios
   bloques `▀` con color real vía `ffmpeg`; primeras líneas de texto; resumen de carpeta), tamaño,
   modificado, «Irá a Wysun/…» y aviso si ya existe en la nube (comprobación asíncrona) → «(2)».
6. **Bandeja**: chip «● N marcados · tamaño» y chips `l` link, `p` contraseña (generada), `d` caducidad
   (no · 1 · 7 · 30 días). Teclas `a` marcar todo, `/` filtrar, `?` ayuda.
7. **Subiendo**: la lista se atenúa y el Detalle muestra barras por elemento, total, velocidad en braille,
   tiempo restante. `Esc` cancela; `b` (o `q`) deja la subida en segundo plano: sigue en la barra y
   avisa por notificación.
8. **Listo**: links subrayados, aviso de copiado, contraseña/caducidad elegidas; `c` copia, `o` abre,
   `↵` vuelve a subir.
9. **Recientes**: agrupado Hoy / Ayer / Esta semana / Antes, icono de link; Detalle con vista previa del
   archivo local (si sigue), link, ruta, origen, tamaño, reglas. `c` copiar, `o` abrir, `k` quitar link
   (OCS DELETE), `n` link nuevo con los chips actuales, `/` filtrar.

## No metas

QR, imágenes con protocolo kitty/sixel, navegar la nube, reanudar entre ejecuciones.

## Cómo (decidido)

- **Subidas como proceso hijo**: la TUI lanza `python -m wysun_drive up … --resultado ARCHIVO` en su
  propia sesión, lee el progreso del archivo de estado de la barra (`wysun-drive/<pid>.json`) y el
  resultado del archivo JSON al terminar. Así `b` solo cierra la TUI y el hijo sigue; antes crea
  `RESULTADO.notificar` para que notifique al terminar (un archivo y no una señal: una señal podría llegar
  antes de que el hijo instale su manejador y matarlo). `Esc` → `SIGTERM` (cancelar).
- `up --origen terminal|files|captura` se guarda en el historial (Files y la captura lo pasan).
- `client.quota()` (PROPFIND Depth 0 en la raíz) y `api.remove_link(remote)`.
- Vista previa: `ffmpeg -frames:v 1 -vf scale,crop -f rawvideo rgb24`, en un hilo, con caché por
  `(ruta, mtime, tamaño)`; sin ffmpeg solo metadatos. Texto: ≤ 64 KB, UTF-8, sin caracteres de control.
- Transparente: `Screen.render(..., transparent_bg=RGB)` omite el fondo de las celdas cuyo fondo es
  exactamente el del lienzo; mezclas y capas no cambian.
- Colores solo de la paleta (`Palette`); los colores de la vista previa son píxeles de la imagen del
  usuario (excepción declarada: muestras de contenido).

## Llamadas mías

Ancho del panel izquierdo 55 % (mín. 44 columnas); bajo 100 columnas se oculta el Detalle salvo al
subir; muestras de velocidad cada 0,5 s (60 muestras); caché de vista previa de 64 entradas.
