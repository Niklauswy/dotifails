# Temas de Wysun

Wysun tiene **dos estilos** y **cinco variantes**. Todas las superficies obedecen la misma selección, sin excepciones: lanzador y modos, utilidades, Music, Files, Settings, pantalla de bloqueo, Wysun Recorder, la barra, los paneles y la captura de pantalla de Quickshell y el instalador.

| Estilo | Variantes | Idea |
|---|---|---|
| **Space Black** | `space-black`, `tokyo`, `severance` | Vidrio tintado y oscuro. Misma estructura; solo cambia la paleta. |
| **Fluent** (tipo Windows 11) | `light`, `dark` | Material opaco, radios 8/12/20, Segoe UI Variable → Inter, 150 ms, sin desenfoque del compositor. `light` es el aspecto de los menús de Wysun Recorder (perlado, acento `#2165D5`); `dark` usa mica oscura con la misma estructura, radios, espaciado, tipografía y movimiento. |

## Elegir y guardar el tema

- **Ajustes → Tema** (`wysun settings theme`): tarjetas de estilo y variantes con vista previa; el cambio es inmediato en todas las aplicaciones abiertas.
- Shell: `wysun shell theme` muestra la selección y `wysun shell theme-settings` abre el selector.
- Se guarda en `~/.config/orbit/theme.json`: `{"style": "fluent", "variant": "dark"}`.
  - Una variante que no pertenece al estilo vuelve a la variante por defecto del estilo (`space-black` → `space-black`, `fluent` → `light`).
  - El formato antiguo `{"id": "tokyo"}` y los alias `azul`, `morado`, `Tokyo`, `Severance` se siguen entendiendo. Se migra solo, con copia en `~/.local/state/orbit/theme-backups/`, escritura atómica y permisos `0600`.
  - `WYSUN_THEME` y `ORBIT_THEME` (en ese orden) anulan el archivo. Ejemplos: `tokyo`, `fluent:dark`.
- No hay modo «auto».
- El fondo personal no se toca: solo se propone el fondo del tema cuando eliges tema desde Ajustes o el instalador. Fluent reutiliza `azul.jpg` (no se añadieron imágenes).

## Fuente única de tokens

`apps/wysun/wysun_theme.json` define, por variante, ~108 tokens semánticos y, por estilo, los tokens de forma y movimiento.

- Colores: `canvas`, `surface`, `well`, `line`, `text`, `muted`, `accent`, `accent_hover`, `selection`, `disabled`, `danger`, `success`, `warning`, `scrim` y los derivados de estado (`hover`, `pressed`, `focus`, `*_soft`…), material (`material_top/mid/bottom/edge/glow/highlight`), categorías (`cat_*`) y los de superficies concretas (`tile`, `card`, `region_*`, `knob_off`…).
- Forma: `radius_s/control/m/l`, `space_*`, `border`, `focus_width`, `shadow_*`.
- Tipografía: `font_family`, `font_mono`, `font_caption/small/body/heading/title`.
- Movimiento: `motion_enter/exit/fast`, `motion_easing`, `motion_lift`, `motion_pulse`, `lock_enter/exit`.
- Iconos: `icon_size`, `icon_stroke`; su color sale de los tokens y se regenera al cambiar de tema.

Los colores se escriben en orden CSS: `#RRGGBB` o `#RRGGBBAA`.

**Copias idénticas** (las apps de captura se instalan por versiones separadas y no importan código de `~/.local/share/orbit/app/`):

| Copia | Ruta |
|---|---|
| Fuente | `apps/wysun/wysun_theme.json`, `apps/wysun/theme_core.py` |
| Recorder | `apps/capture/loomrec/ui/wysun_theme.json`, `apps/capture/loomrec/ui/theme_core.py` |
| Quickshell | `apps/shell/wysun_theme.json` |

`tests/test_theme_tokens.py` comprueba que son idénticas. Al cambiar los tokens, copia el archivo a las tres rutas.

## Adaptadores

| Entorno | Módulo | Cómo se usa |
|---|---|---|
| Qt (Wysun) | `apps/wysun/theme_tokens.py` | `color()`, `font()`, `apply_style(widget, plantilla)`, `on_theme_changed()` |
| Recorder | `apps/capture/loomrec/ui/tokens.py` | Mismo contrato; lee la misma selección. |
| Quickshell | `apps/shell/Appearance.qml` (singleton, `qmldir`) | `Appearance.surface`, `Appearance.radiusM`… `Preferences.qml` lo alimenta desde `theme.json`. |
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
3. **Quickshell**: parte de `apps/shell/ThemeDemo.qml`; añade el tipo a `apps/shell/qmldir`.
   ```qml
   Rectangle { color: Appearance.surface; radius: Appearance.radiusM
       Text { color: Appearance.text; font { family: Appearance.fontFamily; pixelSize: Appearance.fontBody } } }
   ```
4. Nunca escribas un color, radio, tamaño de letra o duración propios. `tests/test_theme_literals.py` falla si aparece un color literal (`#rrggbb`, `rgb()`, `QColor(1,2,3)`, `Qt.white`…).
5. Prueba el widget en las 5 variantes (`WYSUN_THEME=fluent:dark`, etc.).

### Excepciones declaradas

Un color literal solo se admite con una razón en la misma línea (`# theme-exception: motivo`, `// theme-exception: motivo`) o dentro de `# theme-exception-begin: motivo` … `# theme-exception-end`. Hoy son: colores que elige el usuario (muestras, tintas de anotación), color semántico de grabación/estado sobre vídeo, lienzos negros de vídeo, ilustraciones por tipo de archivo, sintaxis de otros programas (Hyprland, CSS, formatos de color), valores de configuración del usuario y artefactos de sistema (icono de aplicación, arranque). Los archivos que no son interfaz se listan en `FILE_EXCEPTIONS` del test.

## Valores finales y contraste (WCAG)

Texto ≥ 4,5:1; componentes de interfaz y foco ≥ 3:1. `tests/test_theme_tokens.py` comprueba 24 pares por variante (los tokens translúcidos se componen sobre el fondo de la variante).

| Variante | canvas | surface | text | muted | accent | on_accent | focus | danger |
|---|---|---|---|---|---|---|---|---|
| Space Black | `#161616` | `#242424` | `#F0F0F0` | `#B0B0B0` | `#D5D5D5` | `#212121` | `#D2D2D2` | `#F0A6AF` |
| Tokyo | `#170F1E` | `#251830` | `#F0E9F6` | `#B1A3BD` | `#D6C1E9` | `#22162C` | `#D3BCE8` | `#F0A6AF` |
| Severance | `#0F1B1E` | `#182B30` | `#E9F3F6` | `#A3B8BD` | `#C1E1E9` | `#16282C` | `#BCDFE8` | `#F0A6AF` |
| Fluent claro | `#F3F6FB` | `#FCFDFF` | `#1C2A3B` | `#596A80` | `#2165D5` | `#FFFFFF` | `#2165D5` | `#AA3547` |
| Fluent oscuro | `#202020` | `#2B2B2B` | `#F3F3F3` | `#C8C8C8` | `#76B4FF` | `#0A1A30` | `#FFFFFF` | `#FF99A4` |

Ratios medidos (variante: texto/canvas · muted/surface · on_accent/accent · accent/surface · focus/surface · danger/surface): Space Black 15,9 · 7,2 · 11,0 · 10,6 · 10,3 · 8,0; Fluent claro 13,4 · 5,4 · 5,4 · 5,3 · 5,3 · 6,2; Fluent oscuro 14,7 · 8,5 · 8,1 · 6,6 · 14,2 · 7,0.

Estados en Fluent oscuro: `hover` `#FFFFFF14`, `fill` `#FFFFFF0F`, `selection` `#2F3D50`, `disabled` `#7A7A7A` (texto deshabilitado, sin requisito de contraste), `success` `#6CCB5F`, `warning` `#F2C36B`, borde de foco blanco de 2 px.

## Reglas de ventana de Hyprland

No cambian. Las ventanas de Wysun ya se dibujan con su propio material y esquinas (la regla `wysun-orbit-panels` pone `rounding = 0` y sin sombra del compositor, y `blur` está desactivado), de modo que Space Black (vidrio) y Fluent (opaco) funcionan con las mismas reglas. Solo se actualizan los colores de borde activo/inactivo (`hypr-theme.lua`) al aplicar un tema desde Ajustes.

## Pruebas

```
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
python3 tests/check_manifest.py
python3 apps/capture/run_tests.py
python3 -m unittest discover -s tests/shell_bridge -t tests
python3 tests/wysun_installed_smoke.py
QT_QPA_PLATFORM=offscreen python3 tests/theme_snapshots.py SALIDA --theme fluent:dark   # capturas para comparar
```
