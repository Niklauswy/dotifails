# Wysun Recorder en QML — diseño

> Estado: borrador para aprobación (2026-11-02). Lo marcado **(decisión del usuario)** lo dijo el usuario; lo marcado
> **(decisión mía)** lo elegí al escribir y puede cambiarse.

## Intención

Quedan dos apps con Qt Widgets: el Recorder y el instalador (el instalador se queda así: corre antes de que exista el
runtime QML). El objetivo del usuario es que **todas las apps de uso diario vayan en QML** sobre WysunM3, con un solo
motor de interfaz y sin Widgets.

Al estudiar el Recorder apareció algo más importante que un cambio de toolkit: **la ventana del Recorder ya no tiene
razón de ser como app de gestión**. Grabar lo hace el shell (`wysun-shell record`: selector, cuenta atrás, HUD); el
Recorder conserva el motor de captura sin ventana (worker, portales, PipeWire, FFmpeg). Lo que queda en la ventana son
tres páginas: biblioteca (Grabaciones, Recientes, Papelera), una página de reproducción que incrusta el reproductor de
Widgets de `wysun_media`, y ajustes. El usuario abre sus videos desde Files y los ve en Wysun Player, y no usa la
biblioteca del Recorder: **(decisión del usuario)** le basta con Files.

El resultado buscado: **Recorder = graba, guarda y tiene ajustes.** Gestionar y reproducir es de Files y del Player.

## Metas

1. `wysun recorder` abre una **ventana de ajustes en QML** (WysunM3, tokens del tema, claro/oscuro y wallpaper en
   vivo), con las mismas opciones que hoy. **(decisión del usuario)**: el Recorder conserva sus ajustes.
2. Al terminar una grabación, el MP4 **se abre solo en Wysun Player**. **(decisión del usuario)**
3. Se retiran del Recorder la biblioteca, la papelera propia, la reproducción incrustada y `--show`.
4. Se borra el reproductor de Widgets de `wysun_media` (`player.py`, `controls.py`, `bar.py`, `menus.py`, `audio.py`,
   `image.py`, `video.py`, `shape.py`, `symbols.py`, `host.py`), que solo seguía vivo por la página de reproducción del
   Recorder (spec del Player, «Lo que se retira»). `wysun_media` queda como motor sin interfaz.
5. Las releases de captura dejan de llevar `wysun_media` y pasan a llevar lo necesario para la ventana QML.

## No metas

- Tocar la captura: worker, portales, PipeWire, FFmpeg, finalización, formatos de proyecto, consentimiento.
- Tocar la barra y el HUD de grabación del shell (`apps/shell/modules/areapicker`, `modules/recorder`).
- Migrar el instalador.
- Hacer del Player un gestor de grabaciones o un editor «tipo Windows Media». **(decisión del usuario)**: eso viene
  después, desde el Player. Aquí solo no estorbarlo: el Player ya abre un archivo con `--start` y `--paused`.
- Mover o borrar grabaciones, proyectos, preferencias o datos privados existentes.

## Anti-metas (sería un fracaso aunque «funcione»)

- Perder una grabación en curso al actualizar: el worker debe seguir con el código de su versión.
- Que una preferencia guardada hoy deje de leerse (el archivo `~/.config/wysun/recorder/preferences.json` y
  `capture-ui.json` siguen igual).
- Que la ventana QML importe código de `~/.local/share/wysun/app/` (regla de las apps de captura).
- Dejar código muerto del Recorder Widgets «por si acaso» (`tests/test_dead_code.py`).

## Cosas pedidas que van aparte

El usuario pidió tres cambios del shell que **no forman parte de este proyecto** y se tratarán después, en este orden
**(decisión del usuario)**: (1) poder parar la grabación con las anotaciones abiertas (hoy `LiveAnnotations.qml` toma
puntero y teclado de toda la salida hasta Esc); (2) preview de la cámara en vivo y arrastrarla para colocarla; (3) un
puntero visual mejor al grabar. Nota para el punto 3: `wysun_recorder/live_cursor.py:12` lanza
`wysun_recorder.ui.live_cursor`, módulo que no existe.

## Estado actual (verificado en el código)

- Se lanza con `wysun recorder` → `PROGRAMS['recorder'] = wysun-recorder` en `bin/wysun`. El lanzador de la release
  (`installer/capture_distribution.py`) fija `PYTHONPATH` a la versión y ejecuta `/usr/bin/python3 -P -m wysun_recorder`:
  Python del sistema, sin QtQuick.
- La release copia `('wysun_recorder', 'assets', 'wysun_media', 'wysun_core')`; en `apps/recorder`, `wysun_core` y
  `wysun_media` son enlaces simbólicos a `apps/python`.
- Widgets: `wysun_recorder/ui/app_window.py` (ventana, barra lateral), `app_library.py` (biblioteca), `app_pages.py`
  (`PlayerPage` y `SettingsPage`), `app_kit.py`, `media_host.py` (tema del reproductor incrustado), `tokens.py`,
  `material.py`, `icons.py`, `motion.py`.
- Siguen en uso fuera de la ventana: `ui/capture_feedback_prefs.py` (`headless.py` importa `load_countdown` y
  `save_countdown`, que usa `--set-pref countdown` del shell) y `ui/instance.py` (instancia única).
- `headless.notify_when_ready` espera el MP4, lanza `notify-send «Grabación guardada»` y abre
  `python -m wysun_recorder --show VIDEO` (`request_show` / `take_show_request` pasan el video por un JSON en el runtime).
- El shell habla con el Recorder por CLI (`--prefs`, `--set-pref`, `--audio-devices`, `--start`, `--notify-when-ready`,
  `--status|--pause|--resume|--stop`): ese contrato **no cambia**.
- Ajustes actuales (`SettingsPage`): Al grabar (micrófono, dispositivo, audio del sistema, cursor, cuenta atrás),
  Cámara (activar, dispositivo, tres opciones de estilo: forma, tamaño, esquina), Calidad (fotogramas, calidad), Archivos
  (carpeta de videos), Privacidad (recordar pantalla autorizada, olvidar permisos), Atajos. Leen y guardan con
  `videolibrary.preferences/save_preferences`, `capture_feedback_prefs.save_countdown`, `schema.camera_style`,
  `headless.devices()` y `consent.clear()`.
- Biblioteca: carpetas de proyecto en `~/.local/share/wysun/recorder/recordings`; la papelera es `.trash` dentro de esa
  carpeta; los MP4 finales van a la «carpeta de videos» (por defecto `~/Videos`).
- Wysun Player acepta `wysun player [--start S] [--paused] -- ARCHIVO` (así lo lanzaba `PlayerPage._external`).

## Diseño

### Al terminar una grabación

`notify_when_ready` sigue esperando el MP4 y avisando, pero en lugar de lanzar `--show` ejecuta el lanzador `wysun`
(`shutil.which('wysun')` o `~/.local/bin/wysun`, como hacía `PlayerPage`) con `player -- VIDEO`; si falla, `xdg-open`.
La release no importa código de `app/`: llama al lanzador, no a `wysun_player`. Se retiran `--show`, `request_show`,
`take_show_request` y `request_path`. Si el Player ya está abierto, la petición va a su cliente de siempre.

### La ventana de ajustes

`wysun recorder` sin argumentos abre una ventana QML de ajustes: una sola página con las secciones de hoy, controles de
WysunM3 y los tokens del tema, sin literales (`tests/test_theme_literals.py`). Instancia única por usuario y pantalla
(`wysun_core.instance`, como hoy). Cambiar de modo o de wallpaper se aplica en vivo.

Los ajustes se guardan igual que hoy y al instante (no hay botón «Guardar»). Los valores salen de las mismas funciones
(`videolibrary`, `capture_feedback_prefs`, `schema`, `headless.devices`, `consent`); la ventana no inventa formatos.
La carpeta de videos se elige con el selector de archivos de Wysun, no con un diálogo hecho a mano. Hoy el selector
(`wysun_files.picker`) no tiene un tipo «carpeta» para el Recorder (acepta documentos, audio con carpeta, medios y
subtítulos) y la release no puede importarlo; cómo se pide (un tipo nuevo en el selector o el portal de archivos desde
QML) lo resuelve el plan.

La ventana usa el `app_id` / clase `wysun-recorder`: lo exigen la regla de ventana flotante y centrada de
`config/.config/wysun/hyprland.lua` y el `StartupWMClass` del `.desktop`.

**Orden de la ventana (decisión mía):** la misma de hoy, de arriba abajo: Al grabar, Cámara, Calidad, Archivos,
Privacidad, Atajos. No es un rediseño: el aspecto lo da WysunM3.

### Empaquetado (decisión mía)

El Recorder se instala en versiones inmutables para que una grabación en marcha conserve su código. Por eso la ventana
QML **viaja dentro de cada release**, igual que hoy `wysun_core`:

- la release lleva `wysun_recorder` (con su `qml/`), `assets`, `wysun_core`, `wysun_qml` y una copia de WysunM3; **ya no
  lleva `wysun_media`**;
- el lanzador de la release sigue usando Python del sistema para todo lo que no es la ventana (`--start`, `--prefs`,
  el worker, etc.): ese camino no carga Qt Quick ni cambia;
- solo la ventana de ajustes se re-ejecuta en el venv QML compartido (`~/.local/share/wysun/qml-runtime`, que es un
  runtime y no código de `app/`), con `wysun_qml.bootstrap.ensure_runtime_python`, como el Player;
- `bootstrap.library_path()` busca WysunM3 en `parents[2]/qml`; dentro de una release esa ruta no apunta a su copia
  (`releases/<hash>/wysun_qml/bootstrap.py` → `releases/qml`). El plan debe resolverlo (variable de anulación o
  ubicación de la copia) sin copiar la lógica a mano.

Para el instalador: `apps/recorder` gana enlaces a `wysun_qml` y a la biblioteca QML, y se actualizan la tupla de
paquetes de `capture_distribution.py`, `tests/check_manifest.py` y las pruebas de distribución.

### Qué se retira

- `wysun_recorder/ui/`: `app_window.py`, `app_library.py`, `app_pages.py`, `app_kit.py`, `media_host.py`, `tokens.py`,
  `material.py`, `icons.py`, `motion.py` y lo que quede sin uso. Se **conservan** `capture_feedback_prefs.py` e
  `instance.py` (los usan el CLI y la ventana nueva; el plan decide si salen de `ui/`).
- De `library.py` / `videolibrary.py`: el listado, renombrar, organizar, borrar a la papelera y restaurar, **si nada del
  motor los usa** (el plan lo comprueba antes de borrar); `preferences`, `save_preferences`, `videos_root` y la
  finalización se conservan.
- El reproductor de Widgets de `wysun_media` listado arriba y `tests/media_host.py`, `tests/wayland_media_case.py`,
  `tests/test_media_{player,controls,image,shape}.py`, `apps/recorder/tests/test_player_component.py`, lo que de
  `test_wayland_ui_backend.py`, `test_recorder_redesign.py` y `test_visual_contract.py` pruebe la ventana Widgets, y
  los apartados de `ARCHITECTURE.md`, `docs/player.md` y `docs/qml-base.md` que los citan.
- Datos: **no se borra nada del usuario**. Los proyectos y la `.trash` de `~/.local/share/wysun/recorder/recordings`
  quedan donde están; los MP4 siguen en la carpeta de videos y Files los ve.

## Pruebas y verificación

- Pruebas QML de la ventana con el Python del venv (`tests/qml/check_recorder_*.py`, descubiertas por el runner
  existente): carga sin advertencias QML; cada control lee y guarda en un HOME temporal; las preferencias existentes
  se leen; cambio claro/oscuro en vivo; instancia única.
- Prueba de `notify_when_ready` con `notify-send` y `wysun` falsos: lanza `player -- VIDEO` y nunca `--show`.
- Prueba de la release: no contiene `wysun_media`; la ventana arranca desde la release con `PYTHONPATH` de la release y
  sin `~/.local/share/wysun/app` (por ejemplo, con `HOME` temporal).
- Suites de `AGENTS.md` en serie, incluida `apps/recorder/run_tests.py`; `./instalar.sh --wysun-only`; abrir de verdad
  la ventana de ajustes y verla en claro y oscuro con dos wallpapers.
- Prueba en vivo de extremo a extremo con medios sintéticos: grabar unos segundos una ventana propia, parar y comprobar
  que el Player abre el MP4.

## Riesgos

- Release con una grabación en marcha durante la actualización: no debe borrarse ni reutilizarse la versión anterior.
- El venv QML no existe (instalación a medias): la ventana de ajustes debe decirlo con el mismo aviso que Music y
  Files y **sin** afectar a grabar (el camino sin ventana no usa Qt).
- Tamaño de la release al llevar WysunM3: aceptable, pero el plan lo mide.

## Lo que se deja a quien construya

- Dónde vive exactamente la copia de WysunM3 dentro de la release y cómo se localiza (ver «Empaquetado»).
- Si `capture_feedback_prefs.py` e `instance.py` salen de `ui/` o se quedan.
- Cómo refleja la ventana un cambio de preferencias hecho mientras está abierta (por ejemplo, desde la barra de
  grabación del shell): releer al recuperar el foco es suficiente.
- Cómo se pide la carpeta de videos al selector (ver «La ventana de ajustes»).
- Texto exacto de los avisos, de la descripción del `.desktop` («Graba y edita videos localmente» ya no es cierto) y de
  la línea `recorder` de la ayuda de `bin/wysun` («biblioteca del Recorder»).
- Divisiones de tareas, orden y commits.
