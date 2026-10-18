# Wysun Recorder y Wysun Screenshot

Fuente integrada de ambas aplicaciones dentro de `dotifails`. El instalador común (`./instalar.sh --wysun-only` desde la raíz) actualiza ambas con el resto de Wysun. No ejecutar los instaladores históricos de `scripts/` para actualizar esta distribución.

Los paquetes `loomrec` y `wybieshot` y sus directorios privados se conservan por compatibilidad. La fuente original de `loom` queda como copia histórica; no es necesaria para instalar o ejecutar Wysun.

- `wysun recorder`: biblioteca y editor; `wysun recorder --quick-record`: barra de preparación.
- `wysun screenshot`: captura y editor; `wysun screenshot --library`: biblioteca.
- Pruebas de esta carpeta: `python3 run_tests.py` (HOME y XDG temporales).

Las notas siguientes describen la arquitectura y los formatos existentes; sus comandos técnicos antiguos siguen siendo compatibles.

# Wysun Recorder — local Linux recorder

Standalone Python/PySide6 application with FFmpeg capture and MP4 rendering. Projects and
recordings stay on this machine. No account, server or upload is involved.

## Launch surfaces

The normal launcher opens the Wysun Recorder library. Opening a recording shows the video
player first, with playback/seek controls and an explicit **Editar video** action. The editor's
**Ver video** action returns to playback without losing saved edits or undo history. A video
is prepared automatically in the background on first open; subsequent opens reuse the local
preview until the saved project changes. Preparation can be cancelled and retried with Play.
Projects with no clips still offer editing. Playback mode does not apply undo/redo shortcuts.
Opening a recording that is still active shows focused capture controls instead: paused
captures offer Resume/Finish, and recording captures offer Pause/Finish with a warning that
the controls may appear in the captured area. Opening an entry never sends capture commands
or renders its active sources. Finished recordings open the player. Missing media and mpv
failures remain visible as an error dialog or in the job strip.

`loomrec --quick-record`
opens only the compact bottom capture bar on the current monitor/desktop; the managed
`Super+Shift+l` binding uses this explicit command. `--record` remains the full setup view
for compatibility. Package names, project locations and `loomrec.desktop` remain unchanged.

The bar shares real monitor, region, camera, microphone/system audio, gains, quality and
countdown settings with the full UI. Escape or the close button cancels a pending countdown.
All bar/popover/setup surfaces disappear before capture starts. Stop uses the existing
capture lifecycle and opens the player. While a capture or background job is active, quick
activation leaves it untouched; invoke the normal launcher for the existing explicit
recording controls/job view. Controls can appear in the captured area when explicitly shown.

Window selection lists application windows across all desktops, including hidden clients, and supports refresh. Choosing one activates its desktop; recording still uses visible screen pixels.
Geometry is rechecked at selection, countdown and immediately before capture. This is a
visible screen crop: covered windows include the covering content, minimized/closed windows
are rejected, and moving/resizing during countdown requires selection again. It is not
independent hidden-window capture. X11 window enumeration additionally requires `xprop`.

## Run

Requires Python 3.11+, PySide6 6.8+, FFmpeg/ffprobe with libx264/AAC, X11, PulseAudio or
PipeWire's Pulse server, `pactl`, `xrandr`, `xdpyinfo` and `xwininfo`. `mpv` is used for
playback by the UI. A Wayland portal backend is not implemented.

```sh
python -m venv --system-site-packages .venv
.venv/bin/pip install -e .
.venv/bin/python -m loomrec
.venv/bin/python -m loomrec --devices
python -m unittest discover -s tests -v
```

No desktop files are changed by launching the application. Optional concentration mode temporarily pauses notifications and restores the prior state after capture ends. A persisted lease and detached watcher also recover the prior notification state if the UI exits unexpectedly; a live capture lock prevents premature restoration. Installation/integration is
an explicit separate action after standalone validation, as requested for this project.

## Install or remove locally

After the standalone UI passes its smoke test and source lives at `/home/nicolas/repos/loom`:

```sh
python scripts/install-local.py --check
python scripts/install-local.py --source /home/nicolas/repos/loom
# Later, remove only installer-owned unchanged application files:
python scripts/install-local.py --uninstall
```

The installer copies source into `$XDG_DATA_HOME/loomrec/bundles/<content-hash>` (default
`~/.local/share/loomrec/bundles/<content-hash>`), creates `~/.local/bin/loomrec`, a standard application-menu
`.desktop` entry and icon. It uses the invoking Python interpreter, checks dependencies
without installing packages, records hashes and refuses to overwrite unrelated or modified
files. Removal preserves recordings, settings and user-modified installed files. Test roots
can be supplied with `--data-home` and `--bin-home`. No Orbit/dotifails source files are
modified, and no window manager or desktop is restarted. The installed Orbit application catalog discovers “Wysun Recorder”; the closed-app
`Super+Shift+l` launcher was physically exercised and opened setup without recording.

## Recording semantics

Choose an X11 monitor or an even-sized root-pixel rectangle. Click a window to select its visible rectangle. A selected window is a **fixed
visible screen crop**: overlaps, tooltips and other windows in that rectangle are recorded;
moving or covering the window changes what is visible. This is not hidden-window capture.
Negative/offscreen selections must be intersected with the current X root; unavailable
areas are rejected. Geometry is checked again on resume. Cursor visibility is configurable (on by default).

Microphone and system monitor sources are independently selectable. They remain separate
PCM tracks in each segment with independent project gains; export mixes them with a
limiter. Webcam is an optional separate video file grouped with its screen segment.
Its location/visibility is editable later. Camera/mic discovery does not prove hardware
recording quality or permissions.

The controller starts an independent recorder process. Closing the UI does not implicitly
stop it. Pause finalizes the current Matroska segment, resume starts another, and stop
finalizes and saves the project. Reopen an active project to reattach controls, or use
`python -m loomrec --status|--pause|--resume|--stop /path/to/project` from another terminal.
Live rewind finalizes a segment, removes the latest requested
timeline seconds without deleting sources, then resumes if recording was active. All inputs use the same epoch timestamp origin; native X11 capture timestamps and
Pulse latency-corrected timestamps are preserved. Audio is resampled against that timeline.
Each segment begins at the latest actual first timestamp among selected streams, eliminating
invented screen/audio preroll. Export subtracts this common in-point rather than independently
resetting each stream. See the upstream [X11 capture clock](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavdevice/xcbgrab.c)
and [Pulse timestamp handling](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavdevice/pulse_audio_dec.c). Do not replace this with per-input timestamp resets.

Projects autosave atomically with fsync. A 256 MiB startup / 128 MiB runtime disk reserve
stops recording before exhausting storage. Device/encoder failures are surfaced in status
and per-segment logs. If the worker is killed, FFmpeg receives SIGINT to finalize media.
To recover after an interruption:

```sh
python -m loomrec --recover /path/to/project-directory
```

Recovery refuses while a recorder owns the project lock, remuxes recoverable segments to
new files and preserves originals. Partial unreadable files are reported, not silently
presented as complete. Recovery is best effort; hardware power loss can still lose buffered
media. Camera segments are also remuxed on recovery when present; physical camera crash recovery is unverified.

## Non-destructive edits and export

`project.json` version 1 references relative media paths. `sources` contain immutable
files, type-relative stream numbers, gain, duration and segment group. Ordered `clips`
select a screen source with `in_s`/`out_s` in source seconds. Timeline duration is the sum
of selected ranges; paused wall time never becomes a clip. Audio/camera sources follow
their segment group. Save edits without rewriting media.

Annotations support timed text, right-pointing arrows, highlights, opaque black masks and
blur. Subtitles use timed text. Annotation times are assembled timeline seconds; normalized
rectangles refer to the final canvas **after** the global crop/zoom. Camera placement uses
the same canvas. Blur is a visual effect, not a guarantee that information cannot be inferred;
use opaque masks for exported redaction. The original source remains unredacted.

`RenderJob(project_path, output).start()` snapshots the project, runs in the background,
and exposes `poll()` with state/progress/error. `cancel()` terminates the current encoder
and removes staging files. MP4 is H.264/AAC with source frame timestamps and native post-crop dimensions.
Standard uses CRF20, high CRF16; compact fits within1280×720/CRF26 without
upscaling. Preview uses native dimensions and the source capture quality. Mixed
source sizes share a canvas padded to fit the largest source, without enlarging
smaller clips. Mixed frame rates retain their individual cadence. Capture keeps
native pixels with compact/standard/high compression (CRF28/20/16). Files are published atomically only on success; existing outputs and source
media cannot be overwritten, including a destination created concurrently. Progress is
clip-based, not a frame-accurate ETA. Preview uses the same renderer.

## Verification matrix (2026-10-17)

| Area | Implemented | Evidence / boundary |
|---|---|---|
| Schema/atomic edits | Yes | Deterministic round-trip, ranges, path escape, invalid rectangle/NaN tests |
| X11 region capture | Yes | Real owned opaque region and full 1920×1080 fixture; mapped geometry and topmost stack checked before capture |
| Live rewind | Yes | Real synthetic capture removed exactly 2.0 timeline seconds while preserving originals and continuing capture |
| Installer | Installed and verified | Canonical source `/home/nicolas/repos/loom`; installed launcher `~/.local/bin/loomrec`, desktop entry and Orbit catalog verified. Closed-app launcher key opens setup. Temporary-root removal tests preserve recordings/settings/modified files |
| Pause/resume | Yes | Latest full-monitor test: two real segments, 8.033s assembled duration; paused interval excluded |
| Separate audio | Yes | Dual synthetic Pulse tracks and independent mic-only/system-only capture; physical mic sound not sampled |
| A/V sync | Yes, tested condition | Latest full-monitor test: source1 +10…20ms, resumed source +37…57ms, export +10…57ms including splice, 1Hz flash/880Hz pulses; tolerance80ms. Prior167ms/83ms failures led to native-clock/common-in-point fixes |
| Capture performance | Sample only | Latest1920×1080 direct-X11 fixture: FFmpeg64.7–69.8% CPU/~127MiB RSS, 8.033s montage; GPU-presented fixture previously consumed ~200% CPU. This does not establish long-session performance |
| MP4 edits | Yes | Renders every annotation type, crop, subtitles, trims/reorder; decoded pixels prove black mask and separate blue camera placement; zero-gain decoded samples are silent |
| Independent playback | Decoded | mpv decoded real fixture export to EOF, 1280×720 video + stereo 48kHz audio, null outputs; not a physical speaker check |
| Silence detection | Yes | Synthetic tone-to-silence boundary detected within 50ms; results remain proposals |
| Cancellation/no overwrite | Yes | Cancellation before start and with active encoder; staging absent, existing target and original source protected |
| Crash recovery | Yes | Recorder SIGKILL during owned synthetic fixture; one finalized segment recovered without errors |
| Webcam | Implemented | V4L2 device discovered; physical camera capture deliberately untested |
| UI/library | Separate module | Offscreen construction/open/trim/undo/redo/close passes. Real drag selector/countdown/global pause-resume-stop produces two clips with every decoded pixel matching fixture (±8); themed mpv preview/seek/play proven at940px. Installed full1920×1080 controller test also passed: countdown, global pause/resume/stop, two clips, every decoded frame matches opaque fixture with no controls |
| Long recordings / low storage | Guards implemented | Failure handling not a physical power-loss or full-disk guarantee |
| Wayland / hardware encoding | No | X11 + software libx264 only |

The first attempted physical fixture used requested Qt coordinates under a tiling WM and
was invalid. It was discarded and its media deleted immediately after pixel inspection.
Only the later verified override-redirect fixture supports the physical claims above.

## Library, editing and capture controls

The Spanish/localizable native interface provides library search, collections, rename,
folder reveal, recovery and reversible trash. Edits autosave with undo/redo. Trim, split,
delete, reorder and join contiguous source ranges; edit timed overlays/subtitles, crop,
camera placement and source gains. Render a preview to play the exact export pipeline in
embedded mpv, with a post-mix waveform and time markers. Review detected silence or
transcript intervals before applying cuts. Local ASR requires your own executable/model.

Capture controls are intentionally hidden to avoid appearing in the recording. While the
application is running, conflict-checked global keys are `Super+Ctrl+Shift` plus `r` (setup/
start when ready), `p` (pause/resume), `s` (stop/edit), `c` (stop/trash), `z` (rewind10s) or
`i` (pause/show state). Controls fail closed if another application owns a key. Override action chords in
`$XDG_CONFIG_HOME/loomrec/shortcuts.json` (default `~/.config/loomrec/shortcuts.json`),
for example `{"pause":"Super+Ctrl+Shift+x"}`. Actions are `record`, `pause`, `stop`,
`cancel`, `rewind`, `status`; Ctrl+Alt+Fn is rejected to protect virtual-terminal shortcuts. Real region
capture verified that main window, selector and tray were hidden before capture.

The separately installed launcher shortcut `Super+Shift+l` opens setup even when the
application is closed. Install only its exact managed stanza with:

```sh
python scripts/desktop-shortcut.py --reload
```

It checks expanded existing bindings, backs up the active SXHKD file, appends one marked
block, and signals only a verified current-user SXHKD process for config reload. It never
changes dotifails source or restarts BSPWM. `--uninstall --reload` removes only that unchanged
block, preserving subsequent edits; the application uninstaller also removes its managed
block. The UI's running-only keys require no permanent SXHKD edits.

## Backlog and optional capabilities

`AnalysisJob` provides cancellable silence detection and optional local whisper.cpp
transcription on the edited audio timeline. Results are proposals, never automatic edits.
SRT import supports existing transcripts. Transcription requires an explicitly supplied
`whisper-cli` and model file: neither is installed on this machine, so actual ASR quality
is unverified. No model downloads or cloud calls occur. Live rewind, static crop/zoom,
quality presets and transcript/SRT data contracts are implemented. Animated zoom keyframes,
Wayland portal capture, hardware encoding and long-session stress testing are outside
the present verified implementation.

Manual physical reproduction (exclusive media slot; only the owned fixture is recorded):

```sh
PYTHONPATH=. python tests/manual_capture_proof.py
python tests/manual_measure_sync.py /tmp/loom-safe-proof-PRINTED_ID
# MODE=mic, MODE=system, MODE=crash and MODE=rewind select additional physical scenarios.
```

The sync script samples decoded flashes at 30Hz and audio RMS at 10ms, matching interior
transitions within 0.5s and asserting at most 80ms error. Unmatched start/end and splice
transitions are printed and require inspection; they are not proof of dropped-frame absence.

## Product references and independent improvements

Official Loom/Atlassian documentation consulted on 2026-10-17:

- [Choose recording mode](https://support.atlassian.com/loom/docs/choose-your-recording-mode/)
  covers screen/camera mode choices.
- [Custom-size video](https://support.atlassian.com/loom/docs/record-a-custom-size-video)
  covers selecting a recording area.
- [Trim while recording](https://support.atlassian.com/loom/docs/trim-your-video-while-recording)
  informs the non-destructive live rewind workflow.
- [Transcription and captions](https://support.atlassian.com/loom/docs/loom-video-transcription-and-closed-captions)
  informs transcript and subtitle editing; this app uses optional local ASR.
- [Trim and edit recordings](https://support.atlassian.com/loom/docs/trim-and-edit-your-recordings/)
  describes trimming, transcript editing and overlays.
- [Edit your Loom video](https://support.atlassian.com/loom/docs/edit-your-loom-video/)
  describes trim and stitch workflows.
- [Hide recording controls](https://support.atlassian.com/loom/docs/hide-the-recording-controls/)
  describes Loom's recording controls and pause/resume shortcuts.
- [Microphone/camera troubleshooting](https://support.loom.com/hc/en-us/articles/10018152163357-Microphone-Camera-issues)
  covers source permissions and device troubleshooting.

These are workflow references, not a claim of feature parity or affiliation. Independent
choices here are local-only storage, editable source tracks, recoverable segment files,
explicit visible-window semantics and no-overwrite exports. Our controls are **not**
automatically excluded from a screen crop, unlike the referenced Loom behavior.

Final deployment: source and installed Python files match; SXHKD launch binding was appended with an exact backup and verified reload, without modifying dotifails source. Final bounded offscreen suite: **37 tests passed in 3.608s**, including isolated UI state, installer preservation, and media pixel/audio assertions. Physical camera/microphone sound, local ASR (executable/model absent), and long sessions remain unverified.


### Fluent Soft redesign validation

The native UI uses a light pearl/blue palette independent of Orbit's current dark theme;
no Orbit configuration is changed. Motion preferences are read from
`LOOMREC_REDUCED_MOTION`, `ORBIT_REDUCED_MOTION`, or `reduced_motion` in the local
Loom/Orbit `appearance.json`, with the Qt animation-duration preference also respected.
Hover transitions last170ms when enabled; there are no repeating recording animations.

The redesign preserves the project schema and shared preview/export renderer. A43-test
regression passed, followed by8 focused visual tests and8 existing UI tests after final
polish. Checks cover940×1054 and1280×800 layouts, expanded settings, keyboard navigation,
text/focus contrast, disabled library actions, localized annotation labels preserving
schema values, fixed dialog actions, and hiding controls before deferred resume.
The earlier physical A/V timing evidence remains engine evidence; styling changes do not
constitute a new long-session or physical microphone/camera validation.

Post-redesign bounded physical UI proof: an owned opaque synthetic region passed actual drag selection, countdown, global pause/resume/stop, two finalized clips, and uniform decoded pixels with no visible controls. Final focused visual tests passed8/8 after the UI freeze. The persistent versioned installer retains previous code directories while atomically switching the managed launcher to the redesigned bundle; an existing active capture is never stopped or inspected for media content.


Versioned upgrades keep previously installed code, including the legacy `loomrec/app`
directory, intact. Uninstall removes unchanged owned files but retains code directories
used by live Loom processes; rerun uninstall after those processes exit to remove them.
Media/settings remain separate and are never removed. The exact launcher shortcut is
**Super+Shift+L**; rerunning `scripts/desktop-shortcut.py --reload` migrates only its unchanged
managed block, checks expanded conflicts, and backs up the prior active SXHKD file.
In-recording Super+Ctrl+Shift r/p/s/c/z/i shortcuts are unchanged.


GUI launches are single-instance per user/X11 display. The private local Unix socket is
protected by a process lock; repeated desktop launches focus the existing window and
`Super+Shift+L` requests its recording options without constructing another recorder or
claiming duplicate global keys. Existing editor/undo state stays in memory. Activation
requests pause before revealing controls during a recording. Super+Shift+L waits for the
recorder's finalized `paused` acknowledgement, then maps a floating **En pausa** controller
with elapsed recorded time, **Reanudar** and **Terminar**. Opening an already paused session
sends no capture command. Resume hides controls and owner popovers, then waits 500ms before
sending resume. A failed pause never reveals the controller; an error badge is possible only
outside the captured rectangle (full-monitor capture has no safe on-screen notification space).
Setup, quick options and countdown show the configured pause/stop shortcuts.
Legacy discovery requires a matching same-user live process and recent status;
multiple candidates require explicit selection. Old active GUI processes and their code bundles
are preserved during updates. Their editor behavior changes only after that session finishes
and the GUI is normally reopened; no running Python GUI is hotpatched.
A stale socket
after a crash is replaced only while holding the instance lock. No network service is used.

On BSPWM, explicit activation unhides and focuses only the requested native window, selecting its desktop without changing global rules. Both cold startup and subsequent local activation use this path.


A persistent single-task strip remains visible above the library/setup/editor during
preview generation, MP4 export or local analysis. It distinguishes the operation, displays
real within-clip FFmpeg progress, and exposes asynchronous cancellation through terminal
success/error/cancelled states. Conflicting edit/render actions are disabled; attempting
to open a project reveals the current task instead of an inaccessible modal warning.
For a render already running in a pre-upgrade GUI, the launcher opens a compatibility
panel with indeterminate progress. Its explicit “Detener render anterior” button rechecks
the GUI-owned FFmpeg PID/start identity before interrupting only that renderer. The older
engine may report an FFmpeg error; projects/originals remain unchanged. It never stops a
capture process and no task is cancelled merely by opening the panel.


### Camera preview, countdown and recording feedback

Selecting a camera opens a local, transient 320×180 preview (10 fps output) in the
setup page or camera popup. It uses one shared device process, writes no frames to
disk and makes no network calls. Closing the preview releases the camera; recording
waits for process exit before claiming that device. Input format is negotiated by
V4L2. Busy, missing and permission failures remain visible.

The 0–30 second countdown is shared by quick/full setup and saved in
`$XDG_CONFIG_HOME/loomrec/capture-ui.json`. A large centered number and Escape/cancel
button appear before capture. The countdown, preview and source controls are hidden
before the existing 500 ms compositor settling interval; zero seconds still waits
for camera release.

Window selection lists normal application windows on **all desktops**, including
hidden/minimized clients. Selecting one restores it and switches to its desktop;
the compact recording controls appear there. Live geometry is checked after
activation and again before recording. BSPWM is supported directly; other EWMH
window managers need `wmctrl` for activation. Window recording remains a visible
screen crop: covering the window or changing desktops affects the recorded pixels.

Area selection uses an unmanaged X11 overlay across the virtual screen, with a
dimmed exterior, clear selected interior, size readout and Escape cancellation.
A compositor is required for the translucent layer. The overlay releases input
and closes before setup returns. Small drags cancel without replacing the previous
selection. The border animates while recording and remains amber/static on pause.

Recording borders and the badge use only rectangles **outside** the captured region.
X11 root capture cannot exclude pixels drawn inside its region. On a fully captured
single monitor, unsafe feedback is suppressed; another monitor may hold the badge.
The video area is never cropped to accommodate controls. Monitor geometry changes
hide indicators defensively. Existing recording shortcuts continue to work.

Verification: synthetic native 640×360 region capture with a visible external border
and badge, centered countdown and camera-release preflight passed; every decoded
frame matched the owned solid fixture within ±8 RGB. Full-monitor suppression and
negative monitor coordinates have deterministic geometry tests. Camera lifecycle was tested with synthetic pipes/FFmpeg. An explicitly authorized
live selection of `/dev/video0` also reached `live`, delivered 320×180 frames and
released the device successfully. Only dimensions/state were recorded; no physical
camera frame was saved or screenshotted. Other camera devices remain unverified.

Bounded pause-first control proof (`tests/manual_controls_proof.py`): real synthetic
640×360 capture, two finalized segments, controller visible only after paused ACK,
500ms hide-before-resume, all decoded frames match the owned opaque fixture (RGB ±8).
Explicit finish opens processed playback; mpv play/pause/seek verified. This is a short
region test, not a new full-monitor or long-session sync benchmark.

Selection regressions: `python -m unittest discover -s tests -p "test_selection.py" -v`.
For an explicit native check, run `PYTHONPATH=. python tests/manual_selection_overlay.py`
in an authorized X11/BSPWM session. It uses only synthetic windows, temporarily
switches desktops and restores focus; it captures no screen, microphone or camera.


### Scoped acrylic deployment

Floating controls, popups and dialogs opt into `_WYBIE_ACRYLIC` (32-bit CARDINAL).
Picom rules match `_WYBIE_ACRYLIC = 1 || _WYBIE_ACRYLIC@ = 1` for blur and
`_WYBIE_ACRYLIC = 0 || _WYBIE_ACRYLIC@ = 0` for explicit matte opt-out.
The selector and recording indicator have separate exact-name exclusions for blur,
shadows and rounded corners. Global desktop appearance is unchanged. Transparency
also requires a live compositor and `~/.config/loomrec/materials.json` with
`{"backdrop_blur": true}`; otherwise surfaces remain opaque.

This machine uses Picom 12.5, GLX and existing dual_kawase strength 3. The scoped
configuration passed diagnostics and a synthetic-only native comparison (stripe
standard deviation 0.427 with blur versus 6.908 without). Exact original compositor
and material settings are retained in `~/.local/state/loomrec/materials-integration.json`.
`python scripts/restore-materials.py` restores them only when the managed versions
remain unchanged. The application uninstaller invokes this helper too; modified
settings are preserved. Restoration defers compositor reload while a recorder exists.
Normal application upgrades keep old bundles and saved projects; an idle GUI is
closed through WM_DELETE and reopened normally. In-memory undo history resets.


### Video workspace and playback

The library now indexes ordinary local videos in `~/Videos` (including subfolders),
plus existing recordings from the legacy XDG library. It excludes hidden working
folders and capture segments. **Nueva grabación** opens the floating capture bar.
Viewing an ordinary file opens it directly in mpv: no copy, project or re-encode is
created. **Editar video** makes a cancellable independent copy into
`~/Videos/.wybie/recordings`; saved edits remain non-destructive. Associated videos
and editable snapshots appear once in the catalogue. Exported MP4s default to the
visible Videos folder. Existing recordings are never moved automatically.

Settings controls the destination for new recordings/exports, quality, frame rate,
countdown, notification concentration and reduced motion. Previous destination
folders stay indexed after changing the destination. The shortcut section shows
configured key combinations and opens the existing `shortcuts.json` configuration;
restart after editing shortcuts. The system reduced-motion preference still applies.

The player has play/pause (Space), mute (M), volume, 0.5–2× speed, seeking and
fullscreen (F; Escape returns). Focus the video for Left/Right five-second seeks.
Playback preferences are separate from edit gains, clip timing and export quality.
Local video deletion moves files into a recoverable private trash; restore refuses
to overwrite an existing destination. Renaming a video changes its catalogue title,
not the original filename. Thumbnail and metadata work runs asynchronously and lazily.

The recording indicator uses selected/countdown/starting/recording/paused states,
with a timer and pause/stop controls where space permits **outside** the capture
rectangle. Full-monitor capture may leave no safe indicator space. X11 recording
still captures a fixed visible screen rectangle: moving focus does not stop it,
but covering that rectangle or changing its desktop changes its recorded contents.

Validation: native player IPC confirmed volume, mute, speed, seek and fullscreen
return with synthetic media. Backend focus independence was physically checked on
one 1920×1080 monitor (3.3 seconds, 31 frames, focus moved between two owned
windows without pausing). Placement on a second monitor has synthetic geometry
coverage only; physical two-monitor recording has not been verified.

### Cursor de presentación (X11)

En **Ajustes → Cursor** o **Opciones rápidas → Cursor**, activa/desactiva
**Mostrar cursor**. `Sencillo` conserva el puntero nativo y el rendimiento
anterior; `Presentación` usa una flecha clara con halo y pulsos de clic;
`Estela` añade un rastro breve. Tamaño y efectos se pueden combinar de forma
independiente. Ocultar el cursor conserva la preferencia del preset, pero no
recoge posiciones ni dibuja efectos. Las opciones quedan fijadas durante la
cuenta atrás y la sesión, incluida la pausa.

Los efectos son locales y optativos. En nuevas grabaciones, los presets mejorados
se ven **en vivo** sobre el escritorio dentro del área elegida y quedan grabados
una sola vez en el vídeo original. No son editables retroactivamente. La superficie
no recibe clics ni foco; el puntero nativo se oculta únicamente dentro del área
mientras está activo el helper. Al salir, pausar o terminar se restaura. No se
observan teclas ni se guardan posiciones fuera del área. El helper vive solo
durante los segmentos de captura y se cierra si termina su proceso padre.

La captura X11 de píxeles visibles incluye intencionadamente estos efectos;
no existe exclusión de ventanas implícita. El proyecto marca esos segmentos
con `cursor_baked` para que vista previa y exportación no dibujen otro cursor.
Los proyectos anteriores con `.cursor.jsonl` mantienen sus efectos posteriores
al grabado; los antiguos sin telemetría no reciben trayectorias inventadas.
Los originales permanecen intactos. Recorte, reordenación y máscaras se aplican
al resultado; las máscaras/desenfoques siguen ocultando también los efectos.
Reducir movimiento de la aplicación solo afecta a la demo de Ajustes.

Se requieren X11/XInput2, XFixes4 y un compositor para los efectos en vivo.
Si el helper no puede iniciarse, se avisa y se graba con el puntero nativo.
Si muere durante la captura, se finaliza ese segmento y se continúa una sola vez
con el puntero nativo; los segmentos anteriores conservan su procedencia. El
reloj compartido de captura audio/vídeo permanece sin cambios. La ruta anterior
de telemetría requiere FFmpeg con libass y conserva sus límites de un millón
de eventos/64MiB. El modo en vivo no escribe trazas de posición.

La calidad de reproducción ya no fuerza720p/30fps: conserva resolución, aspecto
y tiempos del original tras el recorte. La caché incluye la versión del pipeline
y el perfil; los antiguos vídeos originales no se modifican. H.264/yuv420p sigue
siendo compresión con pérdida, no una promesa de píxeles idénticos al escritorio.

Verificación sintética de calidad:1600×900 a60fps conservó60 fotogramas;
vista previa y exportación alta dieron píxeles decodificados idénticos. Mezclar
60/24fps conservó30+12 fotogramas, sus cadencias y un corte a0,500s; el mux AAC
presentó un desplazamiento común de21ms. La prueba de texto de1s midió captura
ultrafast1,803s CPU/97273bytes frente a veryfast2,784s/94795bytes: se conserva
ultrafast, sin extrapolar esa medida a otras máquinas o contenidos. El render
alto de esa muestra midió1,794s CPU/190768bytes y un máximo de procesos hijos
de280796KiB en el proceso de prueba. Las pruebas usan solo contenido sintético;
la verificación física sigue limitada a un monitor. La prueba en vivo confirmó clics a través de
la superficie, foco conservado, salida del área y elevación de otra ventana.
Pausa/reanudación y cierre forzado del helper produjeron tres segmentos con
procedencia vivo/vivo/nativo, sin abortar la captura. Fuente/vista previa/alta
mantuvieron una sola flecha (215/214/214 píxeles claros, borde dentro de1px por
compresión); el fallback nativo mostró47. El recorte/reordenación y máscara
final ocultaron los efectos. Esa muestra de4,098s de vídeo ensamblado midió
2,419s de CPU de hijos y59440KiB de RSS máximo, sin audio ni cámara privados.

Referencia de producto: [Loom/Atlassian documenta resaltado de clics](https://support.atlassian.com/loom/docs/highlight-your-mouse-clicks/).
Estos efectos no se presentan como una capacidad exclusiva de Wybie.

### MP4 automático al detener

Las grabaciones nuevas preparan un MP4 automáticamente al pulsar **Detener**,
también al usar `loomrec --stop DIRECTORIO_PROYECTO` sin la interfaz abierta.
Primero se finalizan los segmentos originales; un proceso separado prepara el
MP4 con la misma ruta de renderizado, calidad nativa, mezcla de audio y efectos
que la vista previa. La interfaz muestra **Preparando MP4**, progreso y después
**MP4 listo**. No se promete disponibilidad instantánea. Cerrar la interfaz no
interrumpe esta preparación.

El MP4 se publica en la carpeta de vídeos configurada (por defecto `~/Videos`)
con un nombre único `Grabacion-FECHA-HORA-ID.mp4`. El destino, título y ganancias
se fijan al comenzar la grabación. La publicación es atómica, nunca sobrescribe
archivos existentes y rechaza destinos sustituidos por enlaces simbólicos.
Los segmentos, el proyecto y los vídeos anteriores permanecen intactos.

Cuando está listo, se puede reproducir y copiar su ruta absoluta desde la
biblioteca. Editar después conserva el MP4 anterior; copiarlo avisa si esos
cambios aún no están incluidos. Las grabaciones anteriores no se convierten en
lote: **Organizar → Preparar MP4** inicia su preparación explícitamente.

Cancelar la preparación conserva las fuentes; un error de codificación o
almacenamiento queda visible y permite **Reintentar**. Cancelar/descartar una
captura no inicia una publicación automática. Pausar o recuperar una captura
interrumpida tampoco publica por sí solo. El archivo separado
`finalization.json` registra estado, progreso, destino y SHA256 del proyecto
renderizado; `ready` solo expone una ruta si el MP4 existe. Un bloqueo por
proyecto evita preparaciones simultáneas y un reintento de un resultado listo
con la misma revisión devuelve el mismo archivo.

Verificación sintética: parada por CLI, sin ventana de grabación, produjo un
MP4 nativo de320×180 con AAC48kHz tras dos segmentos pausa/reanudación. Las
pistas sintéticas440/880Hz con ganancias0,25/1,75 dieron RMS0,18579/0,18605
frente a0,18600 esperado con el limitador existente. Ventanas de200ms fijadas
150ms después de cada corte verificaron ambos tonos sin cruzar la unión.
1,524s de línea de tiempo dieron1,545333s de contenedor, incluido el margen AAC
habitual. Error de destino, cancelación y reintento conservaron hashes de
fuentes y MP4 anterior; no quedaron archivos temporales ni se sobrescribió el
archivo de control existente. No se capturaron micrófono, cámara ni medios
privados; la prueba gráfica se limitó a un monitor físico.
