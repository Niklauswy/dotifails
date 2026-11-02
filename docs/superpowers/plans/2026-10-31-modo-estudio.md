# Modo estudio · plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sesiones de estudio pomodoro en Wysun Shell: panel de preparación, entrada a pantalla completa, píldora con anillo ondulado sobre fullscreen, bloqueo reversible de apps, descansos, salida con pulsación larga y resumen.

**Architecture:** La lógica pura (plan de bloques, máquina de estados de la sesión, reglas de apps) vive en `.pragma library` JS probado con node. Un singleton `services/Study.qml` posee el estado, lo persiste y aplica el bloqueo vía `Hypr`. La UI es un módulo propio `modules/study/` con una ventana overlay transparente por pantalla (como `modules/colors`), cuya máscara de entrada cubre solo lo visible; el panel, la pantalla completa, la píldora y las tarjetas son un mismo objeto que cambia de geometría.

**Tech Stack:** QML/Quickshell (runtime privado Qt 6.9.3), Hyprland 0.55 en Lua, QtMultimedia, Python `unittest` + node para pruebas.

**Spec:** `docs/superpowers/specs/2026-10-31-modo-estudio-design.md` (maquetas en `docs/design/modo-estudio/`).

## Global Constraints

- Colores solo de `Colours.palette.*` / `Colours.tPalette.*`; radios, espaciado, tipografía y duraciones de `Tokens.*` y `Anim`. `tests/test_theme_literals.py` debe pasar; las excepciones llevan `theme-exception: motivo`.
- Probar en modo claro y oscuro y con wallpapers de colores distintos; un cambio de modo o wallpaper se aplica en vivo.
- La superficie `study` se añade solo en `apps/shell/wysun/WysunBridge.qml` (lista `surfaces`); sin lanzadores nuevos.
- Atajo `SUPER + N` en `config/.config/wysun/hyprland.lua` y en la configuración activa `~/.config/wysun/hyprland.lua` (con respaldo, sin tocar otras asignaciones).
- Datos privados: estado `${Paths.state}/study.json`, historial `${Paths.state}/study/sessions.jsonl`, preferencias `${Paths.config}/study.json`. Nada en el repo ni en `app/`.
- Nunca se cierra una ventana del usuario: se mueve a `special:wysun-study` y se devuelve a su workspace original.
- Nunca se bloquean: superficies del shell (layers), clases que empiezan por `wysun` (`wysun-music`, `wysun-files`, `wysun-recorder`, `wysun-settings`…), `xdg-desktop-portal*`, `hyprland-share-picker`, agentes polkit (`polkit-*`, `*polkit*`), ni las apps permitidas.
- Por defecto permitidas: `lectio` (Lectio) y `google-chrome` (Chrome). Duración por defecto 2 h, ritmo 25/5, «Ocultar el tiempo» activado.
- Ritmos: 25/5 (largo 15), 50/10 (largo 20), 90/20 (largo 30), en minutos. Duración de 30 a 240 min en pasos de 30, más «Libre» (`0`).
- Commits solo de las rutas de cada tarea (`git commit -- <rutas>`): el índice tiene cambios ajenos preparados (borrado de Wysun PDF) que no deben entrar.
- No reiniciar Hyprland ni cerrar apps del usuario. Una compilación o suite pesada a la vez (`--jobs 3`).
- Textos de la UI en español, exactamente como en la spec.

## Review Focus

1. **Shell reiniciado o caído en plena sesión**: al volver retoma la sesión con el tiempo correcto, o si ya terminó, devuelve las ventanas. Probado en Task 1 (reanudación por instantes absolutos) y en Task 3 (recuperación de `special:wysun-study`).
2. **Ventana de app no permitida abierta en otro workspace o monitor, o ya en un special propio del usuario**: las de workspaces normales se esconden; las de specials del usuario no se tocan. Task 3.
3. **Suspensión del portátil durante un bloque** (salto grande de reloj): la fase avanza las veces necesarias sin quedarse colgada ni contar el tiempo suspendido como foco más allá del fin del bloque. Task 1.
4. **Pausa a mitad de bloque y reinicio del shell en pausa**: sigue en pausa con el mismo restante. Task 1.
5. **Ventana devuelta cuyo workspace original ya no existe**: va al workspace activo de su monitor, sin errores. Task 3 (`restoreTarget`).

---

### Task 1: Lógica pura de la sesión (`StudyPlan.js`)

**Files:**
- Create: `apps/shell/services/StudyPlan.js`
- Test: `tests/shell_bridge/test_study_plan.py`

**Interfaces:**
- Produces (todas puras, tiempos en ms epoch, duraciones en minutos):
  - `RHYTHMS: {25:{focus:25,brk:5,long:15}, 50:{focus:50,brk:10,long:20}, 90:{focus:90,brk:20,long:30}}`
  - `blockCount(durationMin, rhythm) -> int | null` — `null` si `durationMin === 0` (Libre); si no `max(1, round(d / (focus + brk)))`.
  - `longBreakAfter(blocks) -> int | null` — `ceil(n/2)` si `n >= 4`, si no `null`. En Libre (`blocks === null`) los largos van tras cada múltiplo de 4: lo resuelve `breakMinutes`.
  - `breakMinutes(blockIndex1, blocks, rhythm) -> int` — descanso tras el bloque N (1-based).
  - `summaryLine(durationMin, rhythm) -> string` — copias exactas: `"4 bloques de 25 min · descanso largo a mitad"`, `"1 bloque de 90 min"`, `"Bloques de 25 min hasta que pares"`.
  - `start(config, now) -> session` con `config = {duration, rhythm, allowed:[clase], hideTime:bool}` y `session = {config, blocks, block:1, phase:'focus', phaseStart:now, phaseEnd:now+focus*60000, paused:false, pausedAt:0, focusMs:0, distractions:0, startedAt:now, done:false}`.
  - `tick(session, now) -> session` — si `phase==='focus'` y `now >= phaseEnd`: suma `focus` completo a `focusMs`; si era el último bloque → `phase:'done', done:true`; si no → `phase:'break'` con `phaseEnd = phaseEnd + breakMinutes*60000` (encadenado desde el fin teórico, no desde `now`). Si `phase==='break'` y `now >= phaseEnd` → `phase:'ready'` (espera al usuario; no hay más avance). Repite mientras haya avance (salto de suspensión). Nunca avanza si `paused`.
  - `startNext(session, now) -> session` — desde `ready` o `break`: `block+1`, `phase:'focus'`, `phaseStart:now`, `phaseEnd:now+focus`.
  - `skipToBreak(session, now) -> session` — desde `focus`: suma `now-phaseStart` a `focusMs`; pasa a `break` (o `done` si era el último) con `phaseEnd = now + breakMinutes`.
  - `pause(session, now)` / `resume(session, now)` — `resume` desplaza `phaseStart` y `phaseEnd` en `now - pausedAt`.
  - `stop(session, now) -> session` — `done:true`, suma el foco parcial en curso.
  - `progress(session, now) -> 0..1` del bloque o descanso actual (congelado en pausa); `remainingMin(session, now) -> int` (redondeo hacia arriba).
  - `historyRecord(session, now) -> {start, end, rhythm, blocksDone, blocksPlanned, focusMin, distractions}` (`blocksPlanned` = `null` en Libre).
  - `weekTotals(records, now) -> [7 ints]` minutos de foco de lunes a domingo de la semana de `now` (hora local).

- [ ] **Step 1: Write the failing tests** (patrón de `tests/shell_bridge/test_launcher_logic.py`: leer el JS, quitar `.pragma library`, ejecutarlo con `node`, `skipTest` si no hay node). Casos y valores:
  - `blockCount(120,25)==4`, `blockCount(30,90)==1`, `blockCount(240,50)==4`, `blockCount(60,50)==1`, `blockCount(0,25)===null`.
  - `longBreakAfter(4)==2`, `longBreakAfter(5)==3`, `longBreakAfter(3)===null`; `breakMinutes(2,4,25)==15`, `breakMinutes(1,4,25)==5`, `breakMinutes(4,null,25)==15`, `breakMinutes(3,null,50)==10`.
  - `summaryLine` con las tres copias exactas de arriba.
  - Sesión 25/5 de 2 h: tras `tick` en `t0+25min` → `break`, `phaseEnd == t0+30min`; `tick` en `t0+31min` → `ready`; `startNext` → bloque 2.
  - Salto de suspensión: `tick` en `t0+3h` desde bloque 1 → `ready` tras el bloque 1 (no encadena más focos sin el usuario), `focusMs == 25min`.
  - Último bloque: sesión de 30 min con 25/5 → tras `tick` en `t0+25min` → `done`.
  - Pausa: `pause` en +10 min, `tick` en +40 min sigue en `focus`; `resume` en +40 → `remainingMin == 15`.
  - Reanudación tras reinicio: `JSON.parse(JSON.stringify(session))` y `tick` dan el mismo resultado que sin serializar.
  - `skipToBreak` en +12 min → `focusMs == 12min`, `phase=='break'`.
  - `weekTotals` coloca una sesión del lunes en el índice 0 y otra del domingo en el 6.
- [ ] **Step 2:** `python3 -m unittest tests.shell_bridge.test_study_plan -v` → FAIL (falta `StudyPlan.js`).
- [ ] **Step 3:** Implementar `apps/shell/services/StudyPlan.js` con esas funciones (inmutables: devuelven copias).
- [ ] **Step 4:** Mismo comando → PASS. Añadir también `tests/shell_bridge/test_launcher_logic.py::test_shell_javascript_avoids_lookbehind` en la corrida (debe seguir pasando).
- [ ] **Step 5:** Commit `feat(study): lógica pura de sesiones de estudio`.

### Task 2: Servicio `Study`, superficie y CLI

**Files:**
- Create: `apps/shell/services/Study.qml`
- Modify: `apps/shell/wysun/WysunBridge.qml` (lista `surfaces` + `show()`), `bin/wysun-shell` (caso `study`)
- Test: `tests/shell_bridge/test_dispatcher.py` (añadir casos)

**Interfaces:**
- Consumes: `StudyPlan.js` (Task 1), `Paths.state`, `Paths.config`.
- Produces — singleton `Study`:
  - `readonly property bool active` (hay sesión y no `done`), `property var session`, `property var prefs` (`{duration, rhythm, allowed, hideTime}` con los valores por defecto de Global Constraints), `property real now` (tic de 1 s solo con sesión activa).
  - `readonly property real progress`, `readonly property int remainingMin`, `readonly property string phase` (`'focus'|'break'|'ready'|'done'`), `readonly property var week` (7 ints), `property var lastSummary` (el `historyRecord` de la sesión recién acabada).
  - Señales: `phaseEnded(string from)` (para sonido y destellos), `distraction(string appName, string iconName)`, `requestSetup()`, `requestPill()`.
  - Métodos: `begin(config)`, `startNext()`, `skipToBreak()`, `togglePause()`, `finish()` (guarda historial, `lastSummary`, limpia estado), `savePrefs(p)`.
  - IPC `target: 'study'`: `toggle(): bool` (sin sesión → `requestSetup`; con sesión → `requestPill`), `stop(): bool` (= `finish()` sin confirmación), `status(): string` (JSON con `active, phase, block, blocks, progress`).
- `WysunBridge`: `surfaces` gana `study: ''`; en `show()`, `if (kind === "study") return Study.toggle();` antes del resto (igual que `processes`).
- `bin/wysun-shell`: `study) shift; exec "$runtime" ipc call study "${1:-toggle}" ;;`.

- [ ] **Step 1: Write the failing tests** en `test_dispatcher.py`: `assertIn('study', bridge_surfaces())`; el script `bin/wysun-shell` contiene la línea del caso `study)` que llama a `ipc call study`; `apps/shell/services/Study.qml` define `IpcHandler` con `target: 'study'` y funciones `toggle`, `stop`, `status` (comprobación por regex, como el resto de este archivo).
- [ ] **Step 2:** `python3 -m unittest discover -s tests/shell_bridge -t tests -k study -v` → FAIL.
- [ ] **Step 3:** Implementar `Study.qml`: `FileView` para `study.json` (patrón de `services/Timers.qml`: escribir en cada cambio, leer al arrancar y aplicar `tick`); `FileView`/`Process` para añadir una línea JSON a `sessions.jsonl` (crear `${Paths.state}/study/` con `mkdir -p`) y leerla para `week`; preferencias en `${Paths.config}/study.json`. `Timer` de 1 s con `running: active` que hace `now = Date.now(); session = tick(session, now)` y emite `phaseEnded` al cambiar de fase; al llegar a `done` llama a `finish()`. Las modificaciones de bloqueo las hace Task 3 escuchando `active`.
- [ ] **Step 4:** Mismo comando → PASS; además `python3 -m unittest discover -s tests/shell_bridge -t tests -v` completo → PASS.
- [ ] **Step 5:** Commit `feat(study): servicio de sesión, superficie study e IPC`.

### Task 3: Bloqueo reversible de apps

**Files:**
- Create: `apps/shell/services/StudyApps.js`, `apps/shell/services/StudyBlocker.qml`
- Modify: `apps/shell/services/Hypr.qml` (`cycleSpecialWorkspace` ignora `special:wysun-study`), `apps/shell/modules/overview/` (no listar ese special; localizar el filtro de workspaces de la vista general), `apps/shell/modules/drawers/ContentWindow.qml:27` (`hasFullscreen` también es cierto con `Study.active`: oculta barra y borde como en fullscreen)
- Test: `tests/shell_bridge/test_study_plan.py` (casos de `StudyApps.js`)

**Interfaces:**
- Produces — `StudyApps.js`:
  - `NEVER_BLOCK: [/^wysun/i, /^xdg-desktop-portal/i, /^hyprland-share-picker$/i, /polkit/i]`
  - `isAllowed(windowClass, allowedClasses) -> bool` (sin distinción de mayúsculas; clase vacía → permitida).
  - `toHide(windows, allowedClasses) -> [{address, workspace}]` donde `windows = [{address, class, workspace}]`; excluye las que ya estén en cualquier `special:*`.
  - `restoreTarget(origWorkspace, existingWorkspaceNames, activeOnMonitor) -> string`.
- Produces — `StudyBlocker` (singleton): al pasar `Study.active` a true, `hideAll()` mueve en silencio a `special:wysun-study` las ventanas de `toHide(...)` y guarda `{address, workspace, class}` en `Study.session.hidden` (persistido); escucha `Hypr.onRawEvent` `openwindow` (`ADDRESS,WORKSPACE,CLASS,TITLE`) y esconde al momento lo no permitido, llamando a `Study.distraction(nombreDeLaApp, icono)` con `DesktopEntries.heuristicLookup(clase)`; al pasar a false, `restoreAll()` devuelve cada ventana con `restoreTarget`. Al arrancar el shell sin sesión activa, si `special:wysun-study` tiene ventanas, las devuelve (al workspace guardado si hay registro; si no, al activo del monitor). Mover: `Hypr.usingLua ? hl.dsp.window.move({window="address:0x…", workspace="special:wysun-study", follow=false}) : movetoworkspacesilent special:wysun-study,address:0x…` (ver formato en `modules/windowinfo/Buttons.qml:99`).

- [ ] **Step 1: Write the failing tests**: `isAllowed('Lectio',['lectio'])` true; `isAllowed('brave-browser',['lectio','google-chrome'])` false; `isAllowed('wysun-music',[])` true; `isAllowed('org.kde.polkit-kde-authentication-agent-1',[])` true; `toHide` con una ventana en `special:magic` y una de brave en `"2"` → solo la de brave; `restoreTarget('5',['1','2'],'2')=='2'`, `restoreTarget('1',['1','2'],'2')=='1'`.
- [ ] **Step 2:** `python3 -m unittest tests.shell_bridge.test_study_plan -v` → FAIL en los casos nuevos.
- [ ] **Step 3:** Implementar `StudyApps.js` y `StudyBlocker.qml`; instanciar el singleton al arrancar (referenciarlo desde `Study.qml` o `shell.qml` para que exista sin UI abierta). Aplicar los cambios de `Hypr.qml`, vista general y `ContentWindow.qml`.
- [ ] **Step 4:** Tests → PASS. Verificación en vivo (tras Task 7): con Brave abierto en el workspace 2, `wysun-shell study` → Empezar; `hyprctl clients -j | jq '.[]|select(.class=="brave-browser").workspace.name'` → `"special:wysun-study"`; `wysun study stop` → vuelve a `"2"`. Abrir Brave en sesión → acaba en el special.
- [ ] **Step 5:** Commit `feat(study): bloqueo reversible de apps no permitidas`.

### Task 4: Sonido

**Files:**
- Create: `apps/shell/scripts/make_study_chime.py` (generador; sonido propio, sin entrada en `THIRD_PARTY.md`), `apps/shell/assets/sounds/study-chime.wav`, `apps/shell/assets/sounds/study-chime-soft.wav`
- Modify: `apps/shell/services/Study.qml` (reproducción)
- Test: `tests/shell_bridge/test_study_plan.py` (`test_chimes_exist_and_are_short`)

**Interfaces:**
- `Study.chime(kind)` con `kind ∈ {'end','soft'}` usando `SoundEffect` de QtMultimedia sobre `Quickshell.shellPath("assets/sounds/…")` (o la ruta de assets que ya usen otros módulos), volumen 0.6.
- Sonidos: `end` (fin de bloque) = dos tonos senoidales suaves 660 Hz → 880 Hz, 0,9 s, ataque 20 ms y caída exponencial; `soft` (fin de descanso) = un tono 523 Hz, 0,6 s. 44,1 kHz, mono, 16 bits, generados con `wave` de la librería estándar.

- [ ] **Step 1:** Test: ambos WAV existen, mono, 44100 Hz, duración < 1,2 s y el pico < 0,8 de escala completa.
- [ ] **Step 2:** Ejecutar → FAIL.
- [ ] **Step 3:** Escribir el generador, ejecutarlo, conectar `phaseEnded('focus') → chime('end')` y `phaseEnded('break') → chime('soft')`.
- [ ] **Step 4:** Test → PASS.
- [ ] **Step 5:** Commit `feat(study): avisos sonoros propios`.

### Task 5: Ventana del modo estudio, panel de preparación y entrada

**Files:**
- Create: `apps/shell/modules/study/StudyModule.qml` (Scope + `Variants` sobre `Quickshell.screens`), `StudyWindow.qml`, `Morph.qml` (el objeto que cambia de forma: panel ↔ pantalla completa ↔ píldora ↔ tarjeta), `SetupPanel.qml`, `RhythmGroup.qml`, `Takeover.qml`, `CookieShape.qml`, `Halo.qml`
- Modify: `apps/shell/shell.qml` (instanciar `StudyModule`), `apps/shell/wysun/WysunBridge.qml` (cerrar las demás superficies al abrir el panel, como `close()`)

**Interfaces:**
- Consumes: `Study` (Task 2), `CircularProgress` (`components/controls/CircularProgress.qml`, `wavy: true`), `StyledSlider`, `StyledSwitch`, `Chip`, `StyledText`, `Anim`, `Colours`, `Tokens`.
- `StudyWindow` (por pantalla): `StyledWindow` en `WlrLayer.Overlay`, ancla a los cuatro bordes, `exclusionMode: Ignore`, fondo transparente, `mask: Region { item: morph }` (más el halo, que no recibe entrada), `keyboardFocus: OnDemand` solo con el panel abierto. Propiedad `isPillScreen` = pantalla con foco al empezar.
- `Morph`: `state ∈ {'hidden','setup','takeover','pill','card','msg','break','ready','exit','summary'}`; cada estado fija `x/y/width/height/radius/color` y la transición entre estados usa `Anim` (`Anim.DefaultSpatial` para geometría, `Anim.DefaultEffects` para opacidad/color; `Anim.SlowSpatial` para crecer a pantalla completa y contraerse a píldora). Geometrías: panel = ancho `Tokens`-derivado ≈ 440 px, pegado arriba, radios inferiores `Tokens.rounding.extraLarge`; pantalla completa = toda la ventana, radio 0; píldora = alto 34 px, centrada a `Tokens.spacing.small` del borde superior, `Tokens.rounding.full`; tarjeta = 320×150, radio `Tokens.rounding.large`. Los tamaños fijos se definen como propiedades nombradas en `Morph.qml`, derivadas de `Tokens.padding`/`Tokens.font` donde se pueda.
- `SetupPanel` (opción B de `docs/design/modo-estudio/panel-preparar.html`): título «Sesión de estudio» (`Tokens.font.headline.small`), línea de apoyo `StudyPlan.summaryLine(...)` en vivo; «Duración» con `StyledSlider` de 9 pasos (30…240, Libre) y valor a la derecha; «Ritmo» con `RhythmGroup` (tres botones conectados 25/5 clásico, 50/10 largo, 90/20 profundo; el elegido `m3primary`, radio completo y `Layout.fillWidth` con factor 1.25 animado); «Permitido» con chips de filtro con ✓ (`MaterialIcon "check"`) por cada clase de `prefs.allowed` (nombre e icono vía `DesktopEntries.heuristicLookup`) y chip «Añadir» que despliega una lista filtrable de `DesktopEntries.applications` (guarda `startupClass || id`); «Ocultar el tiempo» con `StyledSwitch`; botón «Empezar» a todo el ancho (alto 56, radio completo, se encoge a `Tokens.rounding.large` al pulsar). Escape cierra el panel.
- Entrada (escena 3 de `flujo.html`): Empezar → `Study.begin(config)` → `morph.state='takeover'` en todas las pantallas (crece desde la geometría del panel; en las pantallas sin panel aparece con fundido) → `Takeover` muestra «Modo estudio» (`Tokens.font.headline.large` ampliado ×2; animar `font.weight` de `Font.ExtraLight` a `Font.Medium` y `font.letterSpacing` de `Tokens.spacing.medium` a 0), la línea de ritmo y los chips en cascada (retardo `Tokens.anim.durations.small/3` entre chips), y dos `CookieShape` (9 y 12 lóbulos, `Shape` con `PathPolyline` recalculada por `FrameAnimation`; amplitud 0.055±0.025 y 0.03±0.015; rotación lenta) con `Colours.palette.m3primary` a baja opacidad. A los ~2,2 s: la pantalla con píldora contrae a `'pill'`; las demás se desvanecen. `Halo`: rectángulo con borde `m3primary` de 1,5 px y opacidad baja permanente mientras `Study.active`, más el barrido: `ConicalGradient`/`ShaderEffect` o un `Shape` con un trazo cuyo `dashOffset` recorre el perímetro desde arriba-centro una vez (≈1,7 s) con `Anim.SlowEffects`.

- [ ] **Step 1:** Prueba de carga: `tests/shell_bridge/test_dispatcher.py::test_study_module_is_wired` comprueba por regex que `shell.qml` instancia `StudyModule` y que `modules/study/*.qml` no contienen colores literales (lo cubre también `test_theme_literals`).
- [ ] **Step 2:** Ejecutar → FAIL.
- [ ] **Step 3:** Implementar los archivos.
- [ ] **Step 4:** `python3 -m unittest tests.test_theme_literals tests.shell_bridge.test_dispatcher -v` → PASS. Verificación visual en vivo tras Task 7 (panel, entrada y halo) en claro y oscuro.
- [ ] **Step 5:** Commit `feat(study): panel de preparación, entrada a pantalla completa y halo`.

### Task 6: Píldora, tarjetas y resumen

**Files:**
- Create: `apps/shell/modules/study/PillCompact.qml`, `PillCard.qml`, `PillMessage.qml`, `BreakCard.qml`, `ExitCard.qml`, `HoldButton.qml`, `Summary.qml`, `WeekStrip.qml`, `EdgeSweep.qml` (barrido sobre el contorno de la píldora; reutilizable por `Halo`)
- Modify: `apps/shell/modules/study/Morph.qml`

**Interfaces:**
- Consumes: `Study.progress/phase/remainingMin/session/week/lastSummary` y señales `phaseEnded`, `distraction`, `requestPill`.
- `PillCompact`: `CircularProgress { wavy: true; implicitSize: 22; value: Study.progress; fgColour: fase==='focus' ? m3primary : m3tertiary }`, texto de fase («Foco», «Descanso», «Pausa»), «N de M» (o «Bloque N» en Libre) en `m3onSurfaceVariant`, y «· X min» solo si `!prefs.hideTime` o con el ojo activado o con el ratón encima (anchura animada).
- Hover sobre la píldora (`HoverHandler`) → `'card'`; al salir → `'pill'`. `PillCard`: «Bloque N de M», fase, barra de bloques, botones pausa/seguir (`togglePause`), saltar (`skipToBreak`), terminar (→ `'exit'`) y ojo.
- `distraction(app, icon)` → `'msg'` durante 2,5 s con «⟨app⟩ esperará al final de la sesión», icono con muelle y `EdgeSweep` una vuelta.
- `phaseEnded('focus')` → dos destellos (anillo exterior `m3tertiary` animado en opacidad) → `'break'`: `BreakCard` en `m3tertiaryContainer`/`m3onTertiaryContainer`, «Descanso», «Bloque N hecho. Levántate, estira, bebe agua.», barra que se vacía con `progress`, «Saltar descanso» (`startNext`). Con `phase==='ready'`: «¿Seguimos?», «Descanso terminado. Cuando quieras, empieza el bloque N+1.», botón «Empezar bloque N+1». Al volver a foco, `EdgeSweep` corto sobre el halo.
- `ExitCard`: «¿Terminar la sesión?», «Llevas N de M bloques. Lo que has hecho se guarda.» (Libre: «Llevas N bloques.»), `HoldButton` «Mantén para salir» (2500 ms; al soltar se vacía a ×3 de velocidad; en Libre es un botón normal «Terminar»), «Seguir».
- Fin (`done` o salir): `'summary'` en la pantalla de la píldora, crecido desde la píldora hasta el panel; «Sesión terminada», fecha larga en español (`Qt.locale("es_ES")`), tres datos (bloques «N / M», tiempo «1 h 40», distracciones), «Esta semana» con `WeekStrip` (L…D, hoy en `m3primary`), botones «Otra sesión» (→ `'setup'`) y «Cerrar» (→ `'hidden'`). El halo se apaga y la barra vuelve (efecto de `Study.active=false`).

- [ ] **Step 1:** `test_dispatcher.py::test_study_copy` verifica por búsqueda literal que las copias exactas de la spec aparecen en `modules/study/` («esperará al final de la sesión», «Mantén para salir», «¿Terminar la sesión?», «Levántate, estira, bebe agua.», «Sesión terminada»).
- [ ] **Step 2:** Ejecutar → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** Tests → PASS. Verificación en vivo tras Task 7.
- [ ] **Step 5:** Commit `feat(study): píldora con anillo ondulado, descansos, salida y resumen`.

### Task 7: Atajo, documentación, despliegue y verificación en vivo

**Files:**
- Modify: `config/.config/wysun/hyprland.lua` (tras la línea de `SUPER + X`: `hl.bind("SUPER + N", hl.dsp.exec_cmd("wysun study"), {description="Wysun | study | Modo estudio: preparar sesión o mostrar la píldora"})`), `ARCHITECTURE.md` y `docs/wysun.md` (sección breve: superficie `study`, servicio, datos privados, recuperación con `wysun study stop`)
- Active config: `~/.config/wysun/hyprland.lua` (respaldo `~/.config/wysun/hyprland.lua.bak-2026-10-31` antes de editar; insertar la misma línea; `grep -c '"SUPER + N"'` debe dar 1)

- [ ] **Step 1:** Suites (en serie): `python3 -m unittest discover -s tests -v`, `python3 -m unittest discover -s tests/shell_bridge -t tests`, `python3 -m unittest discover -s tests/wysun_app -t tests`, `python3 tests/check_manifest.py` → todo PASS (anotar fallos previos ajenos si los hay).
- [ ] **Step 2:** `./instalar.sh --wysun-only` → sin conflictos; `wysun reload`; `pkill -x quickshell; setsid wysun-shell &`; `hyprctl reload` **no** (el atajo nuevo lo carga Hyprland al guardar el Lua; si no, `wysun shell reload-preferences`/recarga de config dinámica del shell).
- [ ] **Step 3:** Verificación en vivo, con capturas `grim` en claro y oscuro: `SUPER + N` abre el panel; Empezar → entrada y píldora; Lectio en fullscreen sigue mostrando píldora y halo; abrir Brave → mensaje en la píldora y Brave en el special; `wysun-shell study status` muestra la fase; saltar al descanso → tarjeta terciaria y sonido; pulsación larga → resumen; Brave vuelve a su workspace. Cambiar el modo claro/oscuro con la sesión activa → colores en vivo. Reiniciar el shell en plena sesión → la retoma.
- [ ] **Step 4:** Commit `feat(study): atajo Super+N y documentación del modo estudio` (solo los archivos de esta tarea; no incluir los cambios ajenos ya preparados en el índice).
