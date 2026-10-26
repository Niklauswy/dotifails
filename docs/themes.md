# Tema de Wysun

Wysun tiene **un solo estilo, Material You** (sistema de diseño Material Design 3; véase más abajo). No hay temas fijos: el color y el acento salen siempre del wallpaper actual y todas las superficies obedecen la misma selección, sin excepciones: lanzador y modos, utilidades, Music, Files, Settings, pantalla de bloqueo, Wysun Recorder, la barra, los paneles y la captura de pantalla de Quickshell y el instalador.

## Lo que elige el usuario

- **Wallpaper**: solo con el carrusel (`Super+Shift+W`, `wysun shell wallpapers` o Ajustes → Wallpaper & style → *Browse as carousel*). Ahí también hay «aleatorio» (`Ctrl+R`) y «añadir imagen». Al aplicar un fondo se regenera el esquema (`wysun scheme refresh`); los fondos de video o GIF usan un fotograma.
- **Modo**: `auto` (lo deduce del brillo del fondo), `light` o `dark`. Es la única opción de color. Si eliges claro u oscuro se queda así aunque cambies de wallpaper, hasta que vuelvas a `auto`.
- **Transparencia** del shell (Ajustes → Wallpaper & style).

No hay variantes de Material (se elige sola según lo colorido que sea el fondo) ni acento manual.

## Sistema de diseño: Material Design 3; Fluent 2 en desarrollo

Toda la interfaz de Wysun se diseña con **Material Design 3 (Expressive)**. Ajustes → Wallpaper & style → *Design system* lo muestra: la tarjeta de Material 3 está seleccionada y es la única opción; la de **Fluent 2** aparece deshabilitada con la marca *WIP* (`apps/shell/modules/nexus/common/DesignSystemPicker.qml`). No se guarda nada: `theme.json` sigue siendo `{"mode": ...}` y ningún lector conoce otro estilo. Cuando Fluent 2 exista habrá que añadir la clave (p. ej. `style`) a la vez en `wysun_core.theme`/`appearance`, el Recorder y `Colours.qml`, con migración, y darle sus propios tokens en `tokens.json` en lugar de condicionales sueltos.

Qué significa para quien añade UI:

- **Color**: solo roles M3 (`Colours.palette.m3*`, o los tokens semánticos de las apps), nunca un color propio.
- **Forma**: `rounding.*` es la escala de forma M3 (`extraSmall` 4, `small` 8, `medium` 12, `large` 16, `largeIncreased` 20, `extraLarge` 28, `extraLargeIncreased` 32, `extraExtraLarge` 48, `full`); «none» es `0`. Botones y chips en píldora (`full`), FAB en `large`, tarjetas y grupos en `extraLarge`.
- **Tipografía**: roles M3 `headline`, `title`, `body` y `label` (`large`/`medium`/`small`). `display` no se define porque el escritorio no tiene texto de ese tamaño; si hace falta, se añade a `tokens.json` y a `appearanceconfig.hpp` a la vez. Pesos que se apartan de la línea base M3: `headline.*` y `title.large` usan 500 (el énfasis de M3 Expressive con Google Sans Flex; la base es 400); `label.*` sigue la base M3 (500); cambiar un peso exige tocar el JSON y el respaldo C++ y reconstruir el runtime.
- **Movimiento**: `anim.durations.small/normal/large/extraLarge` son las M3 *short4/medium4/long4/extraLong4* (200/400/600/1000 ms); `anim.curves.emphasized*` y `standard*` son las curvas M3 y `expressive*` las de los muelles M3 Expressive (*fast/default/slow spatial* y *effects*). En QML usa `Anim { type: Anim.… }`/`CAnim`; una duración o un `Easing.*` literal solo se justifica en animaciones continuas (indicadores, bucles) o coreografías propias (logo, bloqueo).
- **Estados**: capa de estado `StateLayer` (hover 0,08 y onda al pulsar); deshabilitado con contenido al 38 % y contenedor al 10 % de `m3onSurface`, como `ButtonBase`.
- **Componentes**: usa los compartidos de `apps/shell/components/` (botones, `Chip`, `Segmented`, filas, `MaterialIcon`) antes de crear uno; los iconos son Material Symbols Rounded.
- **Apps QML**: usan la base compartida `apps/qml/WysunM3` (mismos roles y tokens, medidas de componente M3 en `Metrics.qml`); se prueban en claro y oscuro con la paleta base y tres semillas sintéticas (`tests/qml`). Hay un solo estilo (`Theme.style` = `material3`); las listas `STYLES` de las pruebas dejan sitio a Fluent 2 cuando exista.

## Dónde se guarda

- `~/.config/wysun/theme.json`: `{"mode": "auto"}` (o `light`, `dark`). Las claves desconocidas se conservan; un archivo sin `mode` válido se lee como `auto`, y `write_mode` lo reescribe con copia en `~/.local/state/wysun/theme-backups/`, escritura atómica y permisos `0600`.
- `~/.local/state/wysun/scheme.json`: roles de Material You generados desde el wallpaper; lo escribe solo `wysun scheme` (`wysun scheme set auto|light|dark`, `wysun scheme refresh`). El shell, las apps Qt y el Recorder lo leen en vivo.
- `WYSUN_THEME=light|dark` fuerza la paleta base sin leer el esquema (pruebas y capturas).
- El fondo por defecto es `assets/backgrounds/purple-abstract-3840x3840-27445.jpg`; una instalación nueva lo usa y el fondo personal no se toca.

## Fuente única de tokens

`apps/python/wysun_core/tokens.json` (`schema: 3`) define una paleta base para `light` y otra para `dark` (~108 tokens semánticos cada una, horneados desde el esquema del fondo por defecto) y los tokens de forma, tipografía y movimiento con **los nombres y valores del shell**. Python los aplana con puntos (`rounding.medium`, `font.body.medium.size`), el mismo camino que en QML (`Tokens.rounding.medium`). El esquema del wallpaper se superpone a la paleta base de su modo (`wysun_core.theme.overlay_material_roles`): la base cubre lo que Material no define y es el respaldo mientras no exista `scheme.json`.

- Colores: `canvas`, `surface`, `well`, `line`, `text`, `muted`, `accent`, `accent_hover`, `selection`, `disabled`, `danger`, `success`, `warning`, `scrim` y los derivados de estado (`hover`, `pressed`, `focus`, `*_soft`…), material (`material_top/mid/bottom/edge/glow/highlight`), categorías (`cat_*`) y los de superficies concretas (`tile`, `card`, `region_*`, `knob_off`…). La paleta de código y terminal (`external.palette`) también sigue al fondo.
- Forma: `rounding.*` (`extraSmall`, `small`, `medium`, `large`, `largeIncreased`, `extraLarge`, `extraLargeIncreased`, `extraExtraLarge`, `full`), `spacing.*` y `padding.*` (las mismas ocho claves sin `full`), `border.width`, `border.focus`. Oscuro: cristal translúcido (`material: glass`); claro: perla opaca (`pearl`).
- Tipografía: `font.family.sans` (Google Sans Flex), `font.family.mono` (CaskaydiaCove Nerd Font), `font.family.icon` (Material Symbols Rounded) y la escala M3 `font.<headline|title|body|label|mono>.<large|medium|small>.{size,weight}`, en **puntos** como el shell. `qt_theme.font('body.medium')` da la `QFont` del rol. Las fuentes van empaquetadas en `wysun_core/fonts/` (apps, instalador y cada release del Recorder) y en `apps/shell/assets/` (el shell), con copias idénticas; licencias en `LICENSES/` y `THIRD_PARTY.md`.
- Movimiento: `anim.durations.*` y `anim.curves.*` (las curvas M3 del shell; `qt_theme.easing('anim.curves.emphasizedDecel')`), `anim.lift`.
- Iconos: `icon.size`, `icon.stroke`; su color sale de los tokens y se regenera al cambiar de tema.
- `palettes.<modo>.scheme`: el esquema M3 completo (claves de `scheme.json`) del fondo por defecto en ese modo; una prueba lo regenera con `wysun_scheme.generate_dynamic`.

`border`, `icon` y `anim.lift` solo los usan las apps Qt.

Los colores se escriben en orden CSS: `#RRGGBB` o `#RRGGBBAA`.

Hay **una sola copia**. Las releases del Recorder llevan su propio `wysun_core` (con `tokens.json`) y nunca importan `~/.local/share/wysun/app/`. El shell usa la misma fuente: el instalador la copia a `~/.local/share/wysun/theme/tokens.json` y el plugin `Wysun.Config` la lee al arrancar (`rounding`, `spacing`, `padding`, `anim.durations`, `anim.curves` → `Tokens.*`); lo que falte o tenga otro tipo conserva el respaldo de `plugin/src/Wysun/Config/tokens.hpp`, que `tests/test_shell_tokens.py` compara con el JSON (también la escala tipográfica de `appearanceconfig.hpp`). No hay override de usuario (`shell-tokens.json` desapareció). `Colours.qml` pinta `palettes.<modo>.scheme` de ese archivo mientras no cargue `scheme.json` (`auto` empieza en oscuro).

## Adaptadores

| Entorno | Módulo | Cómo se usa |
|---|---|---|
| Python sin Qt | `wysun_core/theme.py` | `read_mode()`, `write_mode()`, `active_mode()`, `resolve(mode)`, `resolve_active()`, `read_scheme()`, `write_scheme()` |
| Qt (apps, Recorder, instalador) | `wysun_core/qt_theme.py` | `color()`, `font()`, `apply_style(widget, plantilla)`, `on_theme_changed()`, `watch_theme()` |
| Apariencia | `wysun_core/appearance.py` | `read_appearance()`, `save_appearance()`, `reduced_motion()` |
| Quickshell | `apps/shell/services/Colours.qml` | `Colours.palette.m3*`, `Colours.modePreference`, `Colours.setMode()` |
| Apps QML (PySide6) | `wysun_qml/theme_bridge.py` + `apps/qml/WysunM3` | `ThemeFeed { scheme: bridge.scheme; tokens: bridge.tokens; reducedMotion: bridge.reducedMotion }`, luego `Theme.m3*`, `Theme.rounding.*`, `Label { role }`, `Metrics.*` (`docs/qml-base.md`) |

Las plantillas de hoja de estilo usan `@token`, `@grupo.clave` (`@rounding.medium` → px, `@font.body.medium.size` → pt, `@font.family.sans` entre comillas), `@token/alpha` (0-255) y `@svg(nombre,token)`. `apply_style` guarda la plantilla en el widget y se vuelve a renderizar al cambiar de tema.

## Crear un widget que obedece el tema

1. **Qt (Wysun)**:
   ```python
   from wysun_core.qt_theme import apply_style, color, on_theme_changed
   apply_style(self, 'QFrame#mio { background:@surface; border:@border.width solid @line; border-radius:@rounding.medium; font-size:@font.body.medium.size; }')
   p.setBrush(color('accent'))           # al pintar, siempre se pide el color en ese momento
   on_theme_changed(self.refrescar)      # solo si guardas cachés (pixmaps, iconos, texto derivado)
   ```
2. **Recorder**: lo mismo; su hoja global y `apply_theme(app)` viven en `wysun_recorder/ui/tokens.py`.
3. **Quickshell**: usa `Colours.palette.m3*` y los tokens de forma del shell; nunca un color propio.
4. Nunca escribas un color, radio, tamaño de letra o duración propios. `tests/test_theme_literals.py` falla si aparece un color literal (`#rrggbb`, `rgb()`, `QColor(1,2,3)`, `Qt.white`…).
5. Prueba el widget en claro y oscuro (`WYSUN_THEME=light`, `WYSUN_THEME=dark`) y con wallpapers de colores distintos.

### Excepciones declaradas

Un color literal solo se admite con una razón en la misma línea (`# theme-exception: motivo`, `// theme-exception: motivo`) o dentro de `# theme-exception-begin: motivo` … `# theme-exception-end`. Hoy son: colores que elige el usuario (muestras, tintas de anotación), color semántico de grabación/estado sobre vídeo, lienzos negros de vídeo, ilustraciones por tipo de archivo, sintaxis de otros programas (Hyprland, CSS, formatos de color), valores de configuración del usuario, la paleta fija Severance del bloqueo y del arranque (`severance-scheme.json`) y artefactos de sistema (icono de aplicación, arranque). Los archivos que no son interfaz se listan en `FILE_EXCEPTIONS` del test.

## Contraste (WCAG)

Texto ≥ 4,5:1; componentes de interfaz y foco ≥ 3:1. `tests/test_core_tokens.py` comprueba 24 pares por paleta base (los tokens translúcidos se componen sobre el fondo) y `tests/test_wysun_scheme.py` comprueba los mismos pares con el esquema generado de varios fondos, en claro y oscuro y con las nueve variantes de Material.

| Paleta base | canvas | surface | text | muted | accent | on_accent |
|---|---|---|---|---|---|---|
| Oscuro (`dark`) | `#000000` | `#1a191f` | `#e8e4f0` | `#aca9b5` | `#c6c2ee` | `#3e3c60` |
| Claro (`light`) | `#ffffff` | `#f0ecf6` | `#33313a` | `#605e68` | `#5d5a8b` | `#fcf7ff` |

## Reglas de ventana de Hyprland

No cambian. Las ventanas de Wysun ya se dibujan con su propio material y esquinas (la regla `wysun-panels` pone `rounding = 0` y sin sombra del compositor, y `blur` está desactivado). Los colores de borde activo/inactivo salen de `hypr-theme.lua` (`theme_runtime.theme_files`) y `restore_theme` los pinta con el esquema activo al iniciar Settings.

## Pruebas

```
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
python3 tests/check_manifest.py
python3 apps/recorder/run_tests.py
python3 -m unittest discover -s tests/shell_bridge -t tests
python3 tests/wysun_installed_smoke.py
MUSIC_SNAPSHOT_DIR=SALIDA python3 tests/test_music_material.py   # capturas de Music por esquema (claro y oscuro)
```
