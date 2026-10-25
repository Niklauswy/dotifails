# Tema de Wysun

Wysun tiene **un solo estilo, Material You**. No hay temas fijos: el color y el acento salen siempre del wallpaper actual y todas las superficies obedecen la misma selección, sin excepciones: lanzador y modos, utilidades, Music, Files, Settings, pantalla de bloqueo, Wysun Recorder, la barra, los paneles y la captura de pantalla de Quickshell y el instalador.

## Lo que elige el usuario

- **Wallpaper**: solo con el carrusel (`Super+Shift+W`, `wysun shell wallpapers` o Ajustes → Wallpaper & style → *Browse as carousel*). Ahí también hay «aleatorio» (`Ctrl+R`) y «añadir imagen». Al aplicar un fondo se regenera el esquema (`wysun scheme refresh`); los fondos de video o GIF usan un fotograma.
- **Modo**: `auto` (lo deduce del brillo del fondo), `light` o `dark`. Es la única opción de color. Si eliges claro u oscuro se queda así aunque cambies de wallpaper, hasta que vuelvas a `auto`.
- **Transparencia** del shell (Ajustes → Wallpaper & style).

No hay variantes de Material (se elige sola según lo colorido que sea el fondo) ni acento manual.

## Dónde se guarda

- `~/.config/orbit/theme.json`: `{"mode": "auto"}` (o `light`, `dark`). Las claves desconocidas se conservan.
- `~/.local/state/wysun/scheme.json`: roles de Material You generados desde el wallpaper; lo escribe solo `wysun scheme` (`wysun scheme set auto|light|dark`, `wysun scheme refresh`). El shell, las apps Qt y el Recorder lo leen en vivo.
- Los formatos antiguos ({"style","variant"}, {"id"}, {"dynamic"}) se migran solos a `{"mode"}`, con copia en `~/.local/state/orbit/theme-backups/`, escritura atómica y permisos `0600`. Un tema fijo antiguo pasa a `auto`.
- `WYSUN_THEME` y `ORBIT_THEME` (en ese orden) fuerzan la paleta base `light` o `dark` sin leer el esquema; los nombres antiguos (`tokyo`, `fluent:dark`…) solo se entienden como `dark` o `light`.
- El fondo por defecto es `assets/backgrounds/purple-abstract-3840x3840-27445.jpg`; una instalación nueva lo usa y el fondo personal no se toca.

## Fuente única de tokens

`apps/wysun/wysun_theme.json` define una paleta base para `light` y otra para `dark` (~108 tokens semánticos cada una, horneados desde el esquema del fondo por defecto) y los tokens de forma y movimiento del estilo. El esquema del wallpaper se superpone a la paleta base de su modo (`theme_core.overlay_material_roles`): la base cubre lo que Material no define y es el respaldo mientras no exista `scheme.json`.

- Colores: `canvas`, `surface`, `well`, `line`, `text`, `muted`, `accent`, `accent_hover`, `selection`, `disabled`, `danger`, `success`, `warning`, `scrim` y los derivados de estado (`hover`, `pressed`, `focus`, `*_soft`…), material (`material_top/mid/bottom/edge/glow/highlight`), categorías (`cat_*`) y los de superficies concretas (`tile`, `card`, `region_*`, `knob_off`…). La paleta de código y terminal (`external.palette`) también sigue al fondo.
- Forma: `radius_s/control/m/l`, `corner_*` (escala M3), `space_*`, `border`, `focus_width`, `shadow_*`. Oscuro: cristal translúcido (`material: glass`); claro: perla opaca (`pearl`).
- Tipografía: `font_family`, `font_mono`, `font_caption/small/body/heading/title`.
- Movimiento: `motion_enter/exit/fast`, `motion_easing`, `motion_lift`, `motion_pulse`, `lock_enter/exit`.
- Iconos: `icon_size`, `icon_stroke`; su color sale de los tokens y se regenera al cambiar de tema.

Los colores se escriben en orden CSS: `#RRGGBB` o `#RRGGBBAA`.

**Copia idéntica** (las apps de captura se instalan por versiones separadas y no importan código de `~/.local/share/orbit/app/`):

| Copia | Ruta |
|---|---|
| Fuente | `apps/wysun/wysun_theme.json`, `apps/wysun/theme_core.py` |
| Recorder | `apps/capture/loomrec/ui/wysun_theme.json`, `apps/capture/loomrec/ui/theme_core.py` |

`tests/test_theme_tokens.py` comprueba que son idénticas. Al cambiar los tokens, copia el archivo a la otra ruta. Quickshell no usa el JSON: lee `scheme.json` (`apps/shell/services/Colours.qml`) y la forma sale de sus propios tokens.

## Adaptadores

| Entorno | Módulo | Cómo se usa |
|---|---|---|
| Qt (Wysun) | `apps/wysun/theme_tokens.py` | `color()`, `font()`, `apply_style(widget, plantilla)`, `on_theme_changed()` |
| Recorder | `apps/capture/loomrec/ui/tokens.py` | Mismo contrato; lee la misma selección. |
| Quickshell | `apps/shell/services/Colours.qml` | `Colours.palette.m3*`, `Colours.modePreference`, `Colours.setMode()` |
| Instalador | `installer/visual_widgets.py` | Usa `theme_tokens` del repositorio. |

Las plantillas de hoja de estilo usan `@token`, `@token/alpha` (0-255) y `@svg(nombre,token)`. `apply_style` guarda la plantilla en el widget y se vuelve a renderizar al cambiar de tema.

## Crear un widget que obedece el tema

1. **Qt (Wysun)**: parte de `apps/wysun/theme_demo.py`.
   ```python
   from theme_tokens import apply_style, color, on_theme_changed
   apply_style(self, 'QFrame#mio { background:@surface; border:@border solid @line; border-radius:@radius_m; }')
   p.setBrush(color('accent'))           # al pintar, siempre se pide el color en ese momento
   on_theme_changed(self.refrescar)      # solo si guardas cachés (pixmaps, iconos, texto derivado)
   ```
2. **Recorder**: lo mismo con `from .tokens import apply_style, color`.
3. **Quickshell**: usa `Colours.palette.m3*` y los tokens de forma del shell; nunca un color propio.
4. Nunca escribas un color, radio, tamaño de letra o duración propios. `tests/test_theme_literals.py` falla si aparece un color literal (`#rrggbb`, `rgb()`, `QColor(1,2,3)`, `Qt.white`…).
5. Prueba el widget en claro y oscuro (`WYSUN_THEME=light`, `WYSUN_THEME=dark`) y con wallpapers de colores distintos.

### Excepciones declaradas

Un color literal solo se admite con una razón en la misma línea (`# theme-exception: motivo`, `// theme-exception: motivo`) o dentro de `# theme-exception-begin: motivo` … `# theme-exception-end`. Hoy son: colores que elige el usuario (muestras, tintas de anotación), color semántico de grabación/estado sobre vídeo, lienzos negros de vídeo, ilustraciones por tipo de archivo, sintaxis de otros programas (Hyprland, CSS, formatos de color), valores de configuración del usuario, la paleta fija Severance del bloqueo y del arranque (`severance-scheme.json`) y artefactos de sistema (icono de aplicación, arranque). Los archivos que no son interfaz se listan en `FILE_EXCEPTIONS` del test.

## Contraste (WCAG)

Texto ≥ 4,5:1; componentes de interfaz y foco ≥ 3:1. `tests/test_theme_tokens.py` comprueba 24 pares por paleta base (los tokens translúcidos se componen sobre el fondo) y `tests/test_wysun_scheme.py` comprueba los mismos pares con el esquema generado de varios fondos, en claro y oscuro y con las nueve variantes de Material.

| Paleta base | canvas | surface | text | muted | accent | on_accent |
|---|---|---|---|---|---|---|
| Oscuro (`dark`) | `#000000` | `#1a191f` | `#e8e4f0` | `#aca9b5` | `#c6c2ee` | `#3e3c60` |
| Claro (`light`) | `#ffffff` | `#f0ecf6` | `#33313a` | `#605e68` | `#5d5a8b` | `#fcf7ff` |

## Reglas de ventana de Hyprland

No cambian. Las ventanas de Wysun ya se dibujan con su propio material y esquinas (la regla `wysun-orbit-panels` pone `rounding = 0` y sin sombra del compositor, y `blur` está desactivado). Los colores de borde activo/inactivo salen de `hypr-theme.lua` (`theme_runtime.theme_files`) y `restore_theme` los pinta con el esquema activo al iniciar Settings.

## Pruebas

```
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
python3 tests/check_manifest.py
python3 apps/capture/run_tests.py
python3 -m unittest discover -s tests/shell_bridge -t tests
python3 tests/wysun_installed_smoke.py
QT_QPA_PLATFORM=offscreen python3 tests/theme_snapshots.py SALIDA --theme dark   # capturas para comparar
```
