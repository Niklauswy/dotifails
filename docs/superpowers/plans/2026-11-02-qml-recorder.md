# Wysun Recorder en QML — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Meta:** `wysun recorder` abre una ventana de ajustes en QML (WysunM3); al terminar una grabación el MP4 se abre en Wysun Player; el Recorder deja de tener biblioteca, reproductor y Widgets, y se borra el reproductor de Widgets de `wysun_media`.

**Arquitectura:** la ventana vive en `wysun_recorder/ui/` (reutilizando el nombre: `__main__` no cambia) con un `SettingsController` que lee y guarda las mismas preferencias de hoy. Viaja dentro de cada release de captura junto con `wysun_qml` y una copia de WysunM3 (`qml/`), se re-ejecuta en el venv QML compartido y el resto del CLI sigue con Python del sistema. WysunM3 gana `Switch` y `Dropdown`, que no existían.

**Stack:** PySide6 en el venv `~/.local/share/wysun/qml-runtime`, WysunM3, biblioteca estándar en el CLI.

**Spec:** `docs/superpowers/specs/2026-11-02-qml-recorder-design.md`.

## Restricciones globales

- Colores, radios, espaciado, tipografía y movimiento de los tokens, sin literales (`tests/test_theme_literals.py` escanea `apps/qml` y `apps/recorder/wysun_recorder/ui`; excepción: `theme-exception: motivo`).
- `app_id`/clase de ventana `wysun-recorder` (regla de `config/.config/wysun/hyprland.lua` y `StartupWMClass`).
- La release no importa código de `~/.local/share/wysun/app`. Única excepción: el selector de carpeta se ejecuta como **proceso aparte** (Tarea 3).
- CLI sin cambios: `--prefs`, `--set-pref`, `--audio-devices`, `--start`, `--notify-when-ready`, `--status|--pause|--resume|--stop`, `--recover`, `--devices`, `--record`, `--quick-record`. Formatos de `~/.config/wysun/recorder/preferences.json` y `capture-ui.json` sin cambios.
- No reiniciar Hyprland ni tocar una grabación en curso; no copiar datos privados al repositorio.
- Pruebas QML con el Python del venv: `QT_QPA_PLATFORM=offscreen WYSUN_MPV_OPTIONS=ao=null ~/.local/share/wysun/qml-runtime/bin/python3 -m unittest tests.qml.check_X -v` (los `check_*.py` los descubre `tests/test_qml_runtime.py`; sin registro). Pruebas del Recorder: `python3 apps/recorder/run_tests.py -v -k NOMBRE` (HOME/XDG temporales). Medios sintéticos. Nada de builds ni suites en paralelo.
- Cada commit termina con la línea `Co-Authored-By` que indique la sesión.

## Foco de revisión

1. Preferencias con claves que la ventana no conoce (`previous_video_folders`, `camera_style`, otras): guardar una no borra las demás → Tarea 3.
2. `preferences.json` corrupto, que no sea un objeto, o con `camera_style` inválido: la ventana abre con los valores por defecto, sin excepción → Tarea 3.
3. Sin cámaras ni micrófonos (o sin `pactl`): la ventana abre, la cámara aparece desactivada con su aviso → Tarea 5.
4. Segundo `wysun recorder` con la ventana abierta: enfoca la existente, no abre otra → Tarea 5.
5. Terminar una grabación sin lanzador `wysun` o sin Player: el aviso sale y no hay excepción → Tarea 1.

---

### Tarea 1: Al terminar la grabación, abrir el MP4 en el Player

**Archivos:** modificar `apps/recorder/wysun_recorder/headless.py` (`notify_when_ready`, nueva `open_in_player`); prueba `apps/recorder/tests/test_open_in_player.py`.

**Interfaces:** produce `headless.open_in_player(video) -> bool`. La maquinaria `--show` (`request_show`, `take_show_request`, `request_path`) se queda hasta la Tarea 6, porque la ventana de Widgets aún la consume.

- [ ] **Paso 1: escribir las pruebas** (`PATH` y `HOME` temporales, `wysun`/`xdg-open` falsos que escriben `"$@"` en un archivo):
  - `test_launches_wysun_player_with_the_video`: el falso `wysun` recibe exactamente `player -- <video>`; devuelve `True`.
  - `test_falls_back_to_xdg_open_when_wysun_is_missing`: sin `wysun` ni `~/.local/bin/wysun`, `xdg-open` recibe `<video>`; `True`.
  - `test_returns_false_when_nothing_can_open_it`: sin ninguno, devuelve `False` y no lanza excepción.
  - `test_notify_when_ready_opens_the_player_and_not_the_recorder`: con `wysun_recorder.finalize.status` → `{'state': 'ready', 'output': video}`, `subprocess.run` capturado y `open_in_player` parcheado: `notify-send` recibe `'Grabación guardada'` y el video; `open_in_player` se llama con el video; `--show` no aparece en ningún argv; devuelve el video aunque `open_in_player` devuelva `False`.
- [ ] **Paso 2:** ejecutarlas; esperado: FALLAN (`open_in_player` no existe).
- [ ] **Paso 3: implementar** `open_in_player(video: str | Path) -> bool` en `headless.py`: lanzador = `shutil.which('wysun')` o `~/.local/bin/wysun` si existe; `Popen([lanzador, 'player', '--', str(video)], start_new_session=True, stdin/stdout/stderr=DEVNULL)`; si no hay lanzador o falla con `OSError`, `xdg-open`; `False` si tampoco arranca. En `notify_when_ready`, sustituir el `Popen(... '--show' ...)` por `open_in_player(state['output'])`; el aviso y el valor devuelto no cambian.
- [ ] **Paso 4:** las pruebas PASAN; `python3 apps/recorder/run_tests.py -v -k test_open_in_player`.
- [ ] **Paso 5: commit** `feat(recorder): a finished recording opens in Wysun Player`.

### Tarea 2: El selector de Files acepta carpetas

**Archivos:** modificar `apps/python/wysun_files/picker.py` (docstring y `request_options`); prueba `tests/test_files_picker_folder.py` (mismo estilo que `tests/test_files_picker_audio.py`).

**Interfaces:** produce la petición `{"kind": "folder", "initial": ruta, "title": opcional}` → `request_options` devuelve `('open', title or 'Elegir carpeta', {'current_folder': bytes, 'multiple': False, 'directory': True, 'accept_label': 'Elegir', 'filters': []})`.

- [ ] **Paso 1: pruebas:** `test_folder_request_asks_for_a_directory` (las opciones exactas de arriba, con `title='Carpeta de videos'` respetado); `test_folder_request_starts_from_the_nearest_existing_folder` (`initial=tmp/gone/x` → `current_folder == tmp`); `test_unknown_kind_still_fails` (`ValueError`).
- [ ] **Paso 2:** ejecutar `python3 -m unittest tests.test_files_picker_folder -v`; esperado: FALLA con `Unsupported request kind`.
- [ ] **Paso 3: implementar** la rama `kind == 'folder'` en `request_options`, reutilizando las opciones `directory` que ya usa `audio` y la búsqueda de carpeta existente; actualizar el docstring del módulo.
- [ ] **Paso 4:** PASA, junto con `tests.test_files_picker_audio` y `tests.qml.check_files_chooser`.
- [ ] **Paso 5: commit** `feat(files): the one-shot picker can choose a folder`.

### Tarea 3: SettingsController

**Archivos:** crear `apps/recorder/wysun_recorder/ui/controller.py`; prueba `tests/qml/check_recorder_controller.py` (añade `apps/recorder` **al final** de `sys.path`; `wysun_core` es el mismo código por enlace).

**Interfaces:** consume `Tarea 2`, `headless.set_shell_pref/devices`, `videolibrary.preferences/save_preferences/videos_root`, `capture_feedback_prefs.load_countdown`, `schema.camera_style`, `consent.clear`. Produce:

```python
class SettingsController(QObject):
    valuesChanged = Signal(); devicesChanged = Signal(); pickingChanged = Signal(); message = Signal(str)
    values: QVariantMap    # claves: record_mic, record_mic_device, record_system, record_cursor, countdown, record_camera,
                           # camera_device, camera_corner, camera_shape, camera_size, fps, quality, videos_folder, remember_source
    mics: QVariantList; cameras: QVariantList   # [{id, name}]
    picking: bool
    def __init__(self, picker=None, parent=None)   # picker(initial: str, done: Callable[[list[str]], None]) -> None
    @Slot(str, 'QVariant') def setPref(self, key, value)
    @Slot() def reload(self); @Slot() def chooseFolder(self); @Slot() def forgetPermissions(self)
```

- [ ] **Paso 1: pruebas** (HOME y `XDG_*` temporales con `mock.patch.dict(os.environ)`; `headless.devices` parcheado):
  - `test_defaults_match_the_widgets_page`: `values == {record_mic: False, record_mic_device: '', record_system: True, record_cursor: True, countdown: 3, record_camera: False, camera_device: '', camera_corner: 'bottom-right', camera_shape: 'circle', camera_size: 'medium', fps: 30, quality: 'standard', videos_folder: str(Path.home()/'Videos'), remember_source: True}`.
  - `test_existing_files_are_read`: `preferences.json` y `capture-ui.json` con valores no por defecto → `values` los refleja.
  - `test_set_pref_writes_the_same_files`: `setPref('record_mic', True)` → `preferences.json['record_mic']`; `('countdown', 5)` → `capture-ui.json['countdown'] == 5`; `('camera_corner', 'top-left')` → `camera_style.corner`; `('fps', 60)`; `('quality', 'high')`; `('remember_source', False)`.
  - `test_saving_one_pref_keeps_the_unknown_ones` (foco 1): el archivo trae `previous_video_folders`, `camera_style` y una clave inventada; tras `setPref('fps', 24)` siguen idénticas.
  - `test_invalid_values_emit_a_message_and_change_nothing`: `fps=45`, `quality='x'`, `camera_shape='x'`, clave desconocida → `message` emitido, archivo intacto.
  - `test_corrupt_preferences_fall_back_to_defaults` (foco 2): archivo con basura, con `[]` y con `camera_style: {"shape": "x"}` → construye sin excepción y `values` por defecto (el estilo inválido cae a `camera_style({})`).
  - `test_devices_are_listed`: `devices()` parcheado → `mics`/`cameras`; vacío → listas vacías.
  - `test_choose_folder_saves_it_and_keeps_five_previous`: `picker` inyectado responde `['/tmp/a']` → `videos_folder`, y `previous_video_folders` empieza por la carpeta anterior y tiene ≤ 5; cancelar (`[]`) no cambia nada; `picking` es `True` mientras espera.
  - `test_forget_permissions_clears_consent_and_says_so`: `consent.clear` llamado una vez y `message('Se volverá a pedir permiso para grabar pantallas')`.
- [ ] **Paso 2:** ejecutar; esperado: FALLA (no existe el módulo).
- [ ] **Paso 3: implementar** `SettingsController`. Reparto: las claves `record_*`, `record_mic_device`, `camera_device`, `camera_corner|shape|size` y `countdown` van por `headless.set_shell_pref`; `fps` (15/24/30/60), `quality` (`compact|standard|high`) y `remember_source` por `save_preferences`; `ValueError`/`OSError` → `message`. Si `preferences()` no devuelve un `dict`, tratarlo como `{}`. `chooseFolder` pasa la carpeta actual al `picker`; el predeterminado ejecuta con `QProcess` `[Path(sys.base_prefix)/'bin/python3', '-P', '-m', 'wysun_files.picker']` con `PYTHONPATH=str(paths.data('wysun','app'))`, escribe `{"kind":"folder","initial":..., "title":"Carpeta de videos"}` en stdin y lee `{"code":0,"uris":[...]}` (patrón de `wysun_player/quick/controller.py::_pick`); guardar `videos_folder` y `previous_video_folders` como lo hacía `SettingsPage.choose_folder`.
- [ ] **Paso 4:** PASA.
- [ ] **Paso 5: commit** `feat(recorder): SettingsController for the QML settings window`.

### Tarea 4: `Switch` y `Dropdown` en WysunM3

**Archivos:** crear `apps/qml/WysunM3/controls/Switch.qml` y `controls/Dropdown.qml`; modificar `apps/qml/WysunM3/qmldir`, `Metrics.qml`, `apps/qml/gallery/pages/FieldsPage.qml` (ejemplos), `docs/qml-base.md` (catálogo; quitar «no hay ComboBox» de los límites); prueba `tests/qml/check_selection.py`. Seguir «Cómo extender» de `docs/qml-base.md`.

**Interfaces:** produce `Switch { property bool checked; property bool disabled; signal toggled(bool checked) }` (solo por acción del usuario; pista 52×32, asa 16/24/28 dp según el token M3) y `Dropdown { property var model /* [{value, text}] */; property string current; property string placeholder; property bool disabled; signal activated(string value) }` (campo contorneado de 56 dp, flecha `arrow_drop_down`, abre un `Menu` debajo; flechas, Enter, Espacio y Esc).

- [ ] **Paso 1: pruebas:** `test_switch_size_and_roles` (52×32; encendido: pista ≈ `Theme.m3primary`; apagado: ≈ `m3surfaceContainerHighest`; en `support.palettes()` claro y oscuro); `test_switch_toggles_by_click_and_space_and_emits_once`; `test_disabled_switch_ignores_input`; `test_dropdown_shows_current_text_or_placeholder`; `test_dropdown_opens_a_menu_and_emits_the_chosen_value` (cierra al elegir); `test_dropdown_keyboard` (Abajo abre, Esc cierra sin cambiar `current`); `test_disabled_dropdown_does_not_open`.
- [ ] **Paso 2:** ejecutar; esperado: FALLAN (componentes no registrados).
- [ ] **Paso 3: implementar** ambos con medidas en `Metrics.qml`, colores solo `Theme.m3*`, duraciones con `Motion`, anillo de foco con `FocusRing`, `StateLayer` y `Menu` existentes; registrarlos en `qmldir`; añadir ejemplos a la galería.
- [ ] **Paso 4:** PASA `check_selection`, `check_gallery`, `check_purity` y `python3 -m unittest tests.test_theme_literals`.
- [ ] **Paso 5: commit** `feat(qml): Switch and Dropdown in WysunM3`.

### Tarea 5: La ventana de ajustes en QML

**Archivos:** crear `apps/recorder/wysun_recorder/ui/window.py`, `ui/qml/Main.qml`, `ui/qml/Section.qml`, `ui/qml/SettingRow.qml`; modificar `ui/__init__.py` (`main()` → `window.run()`); prueba `tests/qml/check_recorder_ui.py`. Antes de borrarla en la Tarea 6, leer en `ui/app_window.py` cómo se despacha `Instance.poll` y qué hacía `present()`.

**Interfaces:** consume Tareas 3 y 4 y de WysunM3 `ThemeFeed`, `TopAppBar`, `ListItem`, `Slider`, `Button`, `SnackbarHost`. Produce `window.qml_dir() -> Path` (`ui/qml`), `window.RecorderSettingsWindow(controller=None, engine=None)` con `.window` (raíz `QQuickWindow`) y `present()`, y `window.run() -> int`.

Secciones y filas, en este orden, con los textos de `SettingsPage`: **Al grabar** (micrófono, dispositivo de micrófono con «Predeterminado del sistema», audio del sistema, cursor, cuenta atrás 0–30 s con `Slider`), **Cámara** (grabar con cámara, cámara, esquina, forma, tamaño), **Calidad** (fotogramas por segundo, calidad de video), **Archivos** (carpeta de videos + botón «Cambiar…»), **Privacidad** (recordar pantalla autorizada, botón «Olvidar»), **Atajos** (cuatro filas de texto). Cada control lleva `objectName` igual a su clave de preferencia (`record_mic`, `fps`, `countdown`…) o `chooseFolder` / `forgetPermissions`; los avisos van a `SnackbarHost` (`snackbars`).

- [ ] **Paso 1: pruebas** (venv, `Harness`, HOME y `XDG_*` temporales, `XDG_RUNTIME_DIR` temporal para la instancia):
  - `test_loads_without_warnings_and_lists_every_setting`: ninguna advertencia QML; existen todos los `objectName`.
  - `test_switch_writes_the_preference_file`: clic en `record_mic` → `preferences.json['record_mic'] is True`.
  - `test_dropdown_and_slider_write`: elegir `fps=60` y mover `countdown` a 7 → `preferences.json['fps']`, `capture-ui.json['countdown']`.
  - `test_without_devices_the_camera_rows_are_disabled_and_say_so` (foco 3): con `devices()` vacío, `record_camera` y `camera_device` desactivados, el texto «No se encontró ninguna cámara» visible y la ventana abre.
  - `test_second_launch_focuses_the_open_window` (foco 4): con la instancia reclamada, `run()` envía `focus` y devuelve `0` sin crear otra ventana.
  - `test_light_and_dark_follow_the_theme_live`: `h.use('green-light')` y luego `'green-dark'`; el píxel de fondo de la ventana ≈ `Theme.m3surface` de cada modo.
  - `test_escape_closes_and_focus_reloads_values`: Esc cierra; al volver a activarse la ventana, `reload()` refleja un cambio hecho por fuera (`set_shell_pref`).
  - `test_the_wayland_app_id_is_wysun_recorder`: tras construir `RecorderSettingsWindow`, `QGuiApplication.desktopFileName() == 'wysun-recorder'` (así lo hacen Files, Music y Player; sin esto Hyprland no aplica la regla flotante).
- [ ] **Paso 2:** ejecutar; esperado: FALLAN (no existe `ui.window`).
- [ ] **Paso 3: implementar.** `run()`: `bootstrap.ensure_runtime_python('wysun_recorder', sys.argv[1:])`; `Instance().claim()` (si falla, `request('focus')` y salir con 0); `release_on_termination`, `bootstrap.require_qt()/configure_qt()`, `qml_engine.create_engine('wysun-recorder')` seguido de `app.setDesktopFileName('wysun-recorder')`, `ThemeBridge`, `SettingsController`; contexto `bridge` y `settings`; cargar `Main.qml`; despachar `focus`/`setup` de la instancia a `present()`. `Main.qml`: ventana 640×760 mínima 480×560, `Theme.m3surface`, columna con desplazamiento, `onActiveChanged: if (active) settings.reload()`.
- [ ] **Paso 4:** PASA; ejecutar también `python3 -m unittest tests.test_theme_literals`.
- [ ] **Paso 5: commit** `feat(recorder): settings window on QML (WysunM3)`.

### Tarea 6: Retirar los Widgets del Recorder y el reproductor de Widgets

**Archivos:** borrar `wysun_recorder/ui/{app_window,app_library,app_pages,app_kit,media_host,tokens,material,icons,motion}.py`; borrar `wysun_media/{player,controls,bar,menus,audio,image,video,shape,symbols,host}.py` y los enlaces `apps/recorder/wysun_media`; borrar/recortar pruebas (`tests/media_host.py`, `tests/wayland_media_case.py`, `tests/test_media_{player,controls,image,shape}.py`, `apps/recorder/tests/test_player_component.py`, la prueba del reproductor de `test_wayland_ui_backend.py`, lo de `test_theme.py` y `test_visual_contract.py` que use `ui.tokens`/`ui.material`, `tests/media_benchmark.py` y `tests/media_support.py` si ya solo servían a lo borrado); en `headless.py` y `__main__.py` quitar `--show`, `request_show`, `take_show_request`, `request_path`; en `library.py`/`videolibrary.py` quitar listar, renombrar, organizar, borrar y restaurar **solo si `git grep` no muestra usos fuera de lo que se borra** (`new_directory`, `root`, `videos`, `preferences`, `save_preferences`, `videos_root` y la finalización se quedan); recortar `test_library.py`, `test_video_library.py`; prueba nueva `tests/test_recorder_widgets_retired.py`; docs: `ARCHITECTURE.md` (sección Player/`wysun_media`, Captura, línea de `tests/wayland_media_case.py`), `docs/player.md`, `docs/qml-base.md`, `apps/recorder/README.md` (primera viñeta de `wysun recorder`), spec del Player («Lo que se retira»).

**Interfaces:** `wysun_media` queda sin Qt Widgets; `wysun_recorder.ui` conserva `instance.py`, `capture_feedback_prefs.py` y lo nuevo.

- [ ] **Paso 1: escribir `tests/test_recorder_widgets_retired.py`:** `test_retired_files_are_gone` (la lista de arriba); `test_nothing_references_the_retired_names` (recorre `apps/`, `tests/`, `docs/` salvo `docs/superpowers/` y este archivo: ninguna aparición de `wysun_media.(player|controls|bar|menus|audio|image|video|shape|symbols|host)`, `wysun_recorder.ui.(app_|media_host|tokens|material|icons|motion)`, `request_show`, `take_show_request`, y `'--show'` solo dentro de `apps/recorder` y `bin/`); `test_recorder_ui_does_not_pull_in_qt_widgets` (subproceso del venv: importar `wysun_recorder.ui.controller` y comprobar que `PySide6.QtWidgets` no está en `sys.modules`).
- [ ] **Paso 2:** ejecutarla; esperado: FALLA con la lista de archivos que siguen existiendo.
- [ ] **Paso 3:** borrar y adaptar en este orden, ejecutando `python3 apps/recorder/run_tests.py` y `python3 -m unittest tests.test_dead_code` tras cada bloque: (a) UI de Widgets del Recorder; (b) `--show`; (c) código de biblioteca sin uso; (d) reproductor de Widgets de `wysun_media` y sus pruebas; (e) documentación. Si `tests/test_dead_code.py` marca `wysun_core/ui` como muerto, bórralo aquí y dilo en el commit.
- [ ] **Paso 4:** PASAN `tests.test_recorder_widgets_retired`, `python3 -m unittest discover -s tests -v` (salvo el fallo previo de `test_legacy_names` en `wysun_music/covers.py:91`), `python3 -m unittest discover -s tests/wysun_app -t tests`, `python3 -m unittest discover -s tests/shell_bridge -t tests`, `python3 apps/recorder/run_tests.py` y todo `tests/qml`, uno detrás de otro.
- [ ] **Paso 5: commit** `refactor(recorder): retire the Widgets UI, the embedded player and wysun_media's Widgets player`.

### Tarea 7: Empaquetado de la release y arranque sin runtime

**Archivos:** crear enlaces `apps/recorder/wysun_qml -> ../python/wysun_qml` y `apps/recorder/qml/WysunM3 -> ../../qml/WysunM3`; modificar `installer/capture_distribution.py`, `bin/wysun` (línea `recorder` de la ayuda → «ajustes del Recorder (--quick-record: barra de grabación)»), `tests/test_wysun_distribution.py`, `tests/test_core_packaging.py` (`test_capture_release_ships_theme_data` ya no lee `ui/tokens.py`: comprueba que `wysun_core/tokens.json` y `qt_theme.py` viajan), `tests/check_manifest.py` si nombra archivos.

**Interfaces:** la release pasa a copiar `('wysun_recorder', 'assets', 'wysun_core', 'wysun_qml', 'qml')`; el lanzador añade `export WYSUN_QML_LIB=<release>/qml` antes del `exec`; el `.desktop` dice `Comment=Ajustes de grabación de Wysun`.

- [ ] **Paso 1: pruebas** (en `tests/test_wysun_distribution.py`, con su `Deployment` temporal):
  - `test_release_carries_the_qml_window_and_not_the_media_engine`: existen `wysun_qml/bootstrap.py`, `qml/WysunM3/qmldir`, `wysun_recorder/ui/qml/Main.qml`, `wysun_core/tokens.json`; no existe `wysun_media`; ninguno es un enlace simbólico; el lanzador contiene `WYSUN_QML_LIB=` apuntando a `<release>/qml`.
  - `test_the_release_window_loads_its_own_code_only` (se omite sin venv): con el Python del venv, `PYTHONPATH=<release>`, `WYSUN_QML_LIB=<release>/qml`, HOME temporal y `QT_QPA_PLATFORM=offscreen`, construir `RecorderSettingsWindow()`; todo módulo `wysun*` importado vive bajo la release.
  - `test_without_the_qml_runtime_only_the_window_fails`: con `WYSUN_QML_RUNTIME=/nonexistent`, `wysun-recorder --prefs` sale con 0 y JSON válido; sin argumentos sale con 2 y `stderr` menciona el runtime QML.
  - Adaptar las pruebas existentes de inmutabilidad (las que editan `wysun_media/player.py` en una copia) para editar `wysun_qml/bootstrap.py`.
- [ ] **Paso 2:** ejecutar; esperado: FALLAN.
- [ ] **Paso 3: implementar** el cambio en `capture_distribution.py` y los enlaces; quitar el enlace `apps/recorder/wysun_media` si la Tarea 6 no lo hizo.
- [ ] **Paso 4:** PASAN `tests.test_wysun_distribution`, `tests.test_core_packaging`, `python3 tests/check_manifest.py`. Medir el tamaño de la release antes y después (`du -sh`) y anotarlo en el commit.
- [ ] **Paso 5: commit** `feat(installer): the Recorder release carries the QML window and no media engine`.

### Tarea 8: Desplegar y verificar en vivo

Sin código nuevo.

- [ ] **Paso 1:** suites de `AGENTS.md`, en serie: `python3 -m unittest discover -s tests -v`; `discover -s tests/wysun_app -t tests`; `discover -s tests/shell_bridge -t tests`; `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`; `python3 tests/check_manifest.py`; `python3 apps/recorder/run_tests.py`; `python3 tests/wysun_installed_smoke.py`. Esperado: verdes salvo el fallo previo ya conocido.
- [ ] **Paso 2:** `./instalar.sh --wysun-only`; esperado: sin conflictos y una release nueva en `~/.local/share/wysun/capture/releases/`, sin borrar las anteriores. Después `wysun reload`.
- [ ] **Paso 3:** `wysun recorder`; comprobar con `hyprctl clients -j` que existe una ventana de clase `wysun-recorder`; capturarla con `grim` sobre su región y mirar la imagen. Un segundo `wysun recorder` enfoca la misma. Cambiar un ajuste (cuenta atrás) y comprobar `wysun-recorder --prefs`.
- [ ] **Paso 4:** claro y oscuro sin tocar `~/.config/wysun/theme.json`: capturas fuera de pantalla del mismo `Main.qml` con la paleta clara y la oscura (`Harness.use`) y con dos wallpapers; revisarlas.
- [ ] **Paso 5:** fin de grabación sin grabar la pantalla: con `HOME` temporal y un proyecto sintético ya finalizado (MP4 de `ffmpeg testsrc`), `WYSUN_MPV_OPTIONS=ao=null wysun-recorder --notify-when-ready DIR` debe mostrar el aviso y abrir el MP4 en el Player; cerrar esa ventana.
- [ ] **Paso 6:** pedir al usuario una grabación corta real (`Super+Shift+L`) para confirmar que, al parar, el Player abre el video. Es su prueba de aceptación y no se afirma antes.
- [ ] **Paso 7:** actualizar la memoria `wysun-qml-migration-status` (Recorder hecho; falta el instalador y, más adelante, el Player como gestor) y avisar de los tres cambios del shell pendientes: parar con anotaciones, preview de la cámara con arrastre, puntero visual.
