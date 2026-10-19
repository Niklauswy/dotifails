# Wysun Screenshot

Independent local screenshot product in `wybieshot`, launched with `wybie-screenshot`
or `python3 -m wybieshot`. No Flameshot runtime, recorder worker, audio, network,
accounts or analytics. Recorder source and behavior stay unchanged. Shared visual
style is imported read-only from `loomrec.ui.tokens` / approved materials.

## Architecture / integration contract v1

- `schema.py`: frozen Rect, Layer, CaptureRequest, ActionResult. Layer coordinates
  always refer to the immutable original image, including after crop. Opaque
  colors only. JSON session version 1.
- `capture.py`: Qt QScreen/X11 visible-root pixels. `freeze()` returns image,
  global geometry, monitor rectangles and optional original cursor snapshot.
  `capture(request, frozen)` returns image, geometry, mode and an honest warning.
  Backend takes no keyboard/pointer grabs. UI owns cancellable countdown and selection.
- `document.py`: copied original, immutable layers, undo/redo for layer insertion,
  replacement, removal and crop. All nine tools render before crop. Composition
  creates a new flattened original; comparison requires equal dimensions and
  creates an exportable split bitmap. Their inputs remain separate editable sessions.
- `storage.py`: private local sessions, immutable original PNG + atomic JSON,
  reopening, output/format/countdown/cursor/motion preferences, PNG/JPEG exports and bitmap clipboard. Session
  history is current saved state; undo/redo stack lives in memory, not on disk.
- `ocr.py`: optional installed Tesseract using stdin/stdout and installed languages.
  No downloads. UI must call the potentially slow OCR function in a worker.
- `ui/**`: separate UI owner. Entry point owns QApplication and theme, then calls
  `ui.main.run(app, argv)`.

`Storage.save(doc)` autosaves the current state using a stable session id. UI
calls it after meaningful edits. Library metadata is read locally; corrupt entries
are skipped rather than overwriting or deleting them. Default private source/edit
storage is `$XDG_DATA_HOME/wybie-screenshot/sessions` (normally hidden under
`~/.local/share`), directories 0700, files 0600. Default flattened output is
`~/Pictures/Wybie`, configurable through `Storage.set_output`. Existing images
and other applications' settings are never migrated.

A mask replaces the selected pixels with an opaque solid color in the flattened
export. The private editable session intentionally retains the unredacted original;
share only a reviewed flattened export. Blur is a visual effect, not a guarantee
of irreversible redaction.

## Current capture boundary

The historical X11 backend requires xcb at1×. The native Wayland portal backend described in the capture README reads actual PipeWire frame pixels and maps selection coordinates independently; real compositor capture is still pending verification. Unsupported X11 high/mixed DPR fail
explicitly, without returning misregistered pixels. Monitor and region coordinates
are global root pixels. Negative origins are supported by the frozen-image crop
contract. Physical multimonitor and mixed-DPI capture are not yet verified.
Window capture is a visible client rectangle of a currently mapped window,
including anything covering it; hidden/minimized/off-desktop content is not
reconstructed, and WM decoration/shadow pixels are not included. Xlib support is
optional for window enumeration (`python-xlib`). Cursor inclusion requires XFixes;
for region selection it uses the cursor at freeze time.

Countdown is a UI QTimer; synchronous capture rejects nonzero `delay_ms` so it
cannot block an Escape cancellation. No permanent desktop hook is installed.

## Reproducible coexistence install

Requires Python >=3.11 and PySide6 >=6.8,<7. Install dependencies through the
system/package environment explicitly; the installer never runs pip/apt or fetches
models. `python-xlib >=0.33` is optional for window selection. System X11/XFixes
libraries and Qt xcb platform dependencies are required for capture.

From an integrated source tree:

```sh
python3 scripts/install-screenshot.py --dry-run
python3 scripts/install-screenshot.py
~/.local/bin/wybie-screenshot
```

Installation uses content-addressed releases beneath
`~/.local/share/wybie-screenshot/releases`, a dedicated executable,
`wybie-screenshot.desktop`, and its own SVG icon. Shared theme code is a snapshot
inside that release, so an installed Recorder is not required. A manifest detects
modified/foreign files and refuses to overwrite them. Earlier release trees remain
available; the launcher selects the current version. No auto-start, BSPWM restart,
Picom edits or installed Orbit source edits. Orbit discovers normal desktop entries
on refresh/reopen through its existing application scan.

The screenshot installer does not assign shortcuts. On explicit user request,
`scripts/migrate-screenshot-shortcuts.py` replaces the four existing Flameshot
region commands in active/source sxhkd configuration, without adding any chord.
See the authorized shortcut migration below. Recorder Super+Shift+L is preserved.

```sh
python3 scripts/install-screenshot.py --uninstall --dry-run
python3 scripts/install-screenshot.py --uninstall
```

Uninstall removes only manifest-owned, unmodified files in allowed locations and
preserves session/edit data, preferences, exports, modified files and Recorder.
Previous release code remains on disk when not owned by the latest manifest.

## Flameshot comparison evidence

Inspected installed Flameshot v12.1.0 (Debian build), config and active/source
sxhkd bindings. Preserved the existing `~/.local/bin/flameshot-ctrl-click` helper,
which uses XTEST only while a focused Flameshot override-redirect capture overlay
is present and releases its injected button on overlay exit. It remains started
by the existing bspwmrc; no Wybie behavior is added to it.

Official current docs already describe arrows, text, rectangle/ellipse, pen,
highlight, blur/pixelation, incrementing counters, solid boxes, pin, clipboard,
delay and save. These are parity features, not claimed Wybie inventions:

- https://flameshot.org/
- https://flameshot.org/docs/advanced/commandline-options/
- https://flameshot.org/docs/guide/key-bindings/
- https://flameshot.org/docs/advanced/protecting-your-privacy/

Wybie's product focus here is a persistent editable document library plus local
multi-capture composition and exportable before/after comparison. No claim is
made that those concepts are exclusive across other screenshot software.

## Verification

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_wybieshot*.py' -v
```

The reproducible native proof is `python3 tests/manual_screenshot_proof.py --owned-fixture`
(reserve the native slot first; it refuses active media capture and retains no image).
Optional installed Tesseract was also verified against the generated text
`WYBIE LOCAL 123` with exact recognition, without reading any desktop pixels.

The first native proof used an owned opaque synthetic window, verified X11 actual
geometry, IsViewable, override-redirect and topmost status before capturing only
its interior (88,88,304,224). Two exact RGB colors, PNG roundtrip and clipboard
QImage equality passed. Proof image was temporary and deleted. This first proof established the X11 crop/PNG/clipboard path.

Final integrated validation also passed real frozen-region selection, drawing an
arrow, undo/redo, bitmap copy, PNG export, session reopening, bounded real library
thumbnails, composition dialog and result, before/after slider and saved view,
and persisted JPEG/countdown/cursor/motion settings, using only an owned opaque
full-desktop fixture. Evidence is stored outside the repository. The autosave
failure fix preserves the current document, layers, undo/redo and editor context,
blocks replacement/library navigation/close on failure, and permits retry and
reopening when storage recovers. Tests comprise 16 backend/install and 12 UI cases;
the combined pre-fix run passed 27, followed by focused corrected-save testing.

Installed release **36e94d315820012a7f99** contains 48 manifest-verified files.
Installed UI matches the critical save-error fix `732c37b` (integrated here as
`4810653`); test assertions `4916764` are integrated as `f88f580`. From `/tmp`, the
real installed executable opened quick mode with focus and exited 0 on Escape;
`--library` opened and exited 0 on WM close. Keyboard and pointer grabs were
available after shutdown and focus no longer referenced closed application windows.
SHA256 comparisons preserved 27 Recorder/Flameshot/desktop configuration files.
No private media was read. The initial installation left shortcuts unchanged;
the later explicitly authorized migration is described below. Picom, BSPWM and
Orbit source remain unchanged.

Physical multimonitor capture, window-capture occlusion behavior, cursor inclusion,
Wayland and high/mixed DPI have not been physically verified. The historical physical verification below only covers X11/xcb at1×; it is
supported at runtime. AO native code review was not executed because it requires
a published PR and this delivery is local-only. Visual review by the orchestrator
is not an automatic code approval.


## Authorized Flameshot shortcut replacement

The later user request replaces existing bindings only. All four were region
captures; no monitor/window binding existed. Commands now invoke
`"$HOME/.local/bin/wybie-screenshot" --region --delay 0` directly:

| Existing key | Previous action | New direct action |
| --- | --- | --- |
| Super+Shift+S | `flameshot gui -s -p ~/Screenshots -c` | Add `--accept-on-select --clipboard --path "$HOME/Screenshots"` |
| Super+Shift+Q | `flameshot gui -s -p ~/yurai/scshot -c` (active) | Add `--accept-on-select --clipboard --path "$HOME/yurai/scshot"` |
| Super+Shift+A | `flameshot gui` | Region selection and in-place floating annotation palette |
| Print | `flameshot gui` | Region selection and in-place floating annotation palette |

The source sxhkd configuration already used `~/Screenshots` for Super+Shift+Q;
that source-specific destination is intentionally retained. No user output path
is normalized. S/Q accept on mouse release, save a new PNG without overwrite and
copy its bitmap. Their invocation-specific delay/output settings do not overwrite
stored application preferences. A/Print show editing directly on the frozen selection, using a floating palette;
there is no transition to the large document editor.
Escape cancels direct invocation and ends its process, without opening the bar.

On X11 without a clipboard manager, a completed copy keeps one hidden selection
owner alive until another copy replaces it, as with xclip. This intentional
clipboard ownership has no input grabs, visible launcher or polling loop.
Flameshot remains installed. Its Ctrl/XTEST helper is unchanged and still matches
only the focused Flameshot overlay, so it does not synthesize clicks in Wybie.

Migration creates byte-exact active/source backups with SHA256 before/after
checks, rejects unknown actions/duplicate expanded target chords, validates the
new shell commands, then reloads only SXHKD using SIGUSR1. Literal backslash-t
prefixes on the old S/Q commands are repaired only on those replacement lines.
Unrelated source dirt is preserved. Re-running against migrated files refuses to
add duplicate bindings; recovery inspects the existing manifest rather than
applying again.

```sh
python3 scripts/migrate-screenshot-shortcuts.py              # prepare/dry-run before migration
python3 scripts/migrate-screenshot-shortcuts.py --apply      # only with explicit authorization
python3 scripts/migrate-screenshot-shortcuts.py --restore /path/to/backup
```

Restore first requires that both current configs still match the recorded
post-migration hashes, preserving later user edits instead of blindly overwriting.

Native shortcut proof: `python3 tests/manual_wybieshot_shortcuts.py --owned-fixture`.
After reboot all four real XTEST key chords launched the installed direct region
overlay; Escape ended each process and keyboard/pointer grabs were available.
The owned opaque fixture's actual root geometry, IsViewable, override-redirect and
topmost state were verified before every capture. The proof cancelled all four:
clipboard owner, preferences and sessions stayed unchanged. Actual accepted PNG/
clipboard final actions are tested separately with offscreen synthetic images;
the native shortcut test deliberately does not overwrite the user's clipboard.


## Floating capture workflow and repeat protection

Normal application launch still shows the quick bar. Region captures from that
bar, Super+Shift+A and Print now edit directly on the frozen desktop: drag a
region, then choose an annotation tool on its floating palette. No dedicated main
editor window opens on this path. Explicit library/image editing remains available
without deleting or migrating existing sessions. S/Q retain immediate accept/save/
copy behavior and their established output paths.

The palette reuses Document/Canvas tools: object selection/movement, arrow,
rectangle, ellipse, pen, highlight, text, editable numbered steps, opaque mask,
visual blur, color, thickness/text size and undo/redo. Copy and Save operate only
on original region pixels plus document layers, excluding palette, dimming and
selection controls. An explicit Save dialog chooses the flattened destination;
existing files are never overwritten. On save error, the overlay, document and
capture lease remain available for retry. Region geometry can be adjusted before
annotations; once objects exist, the area control is disabled with an explanatory
tooltip. Undoing all objects enables it again, without silently discarding edits.

`instance.py` holds a private per-user/per-display flock lease through selection
and in-place editing. Direct CLI invocations claim it before QApplication is
created: repeated hotkeys are ignored without opening another overlay or taking
focus. Normal quick-bar capture uses the same lease. Cancel, close, successful
save/copy, initialization failure/process exit release ownership; kernel locking
also recovers after process death. The intentional hidden X11 clipboard owner
does not retain the capture lease, so it cannot block the next screenshot.

Runtime freeze `1078b7d` is installed as release **5e7d9dc1a07ad354f322**. A native
owned-fixture proof pressed real SXHKD chords, repeated a capture shortcut during
both selection and annotation, and checked that one process/overlay and the drawn
object remained. Escape ended each process with keyboard/pointer grabs available.
An additional in-process installed-runtime save used a controlled file-picker
result with real capture, rendering, PNG encoding and storage: region dimensions,
opaque-mask and untouched-source pixels matched exactly, with no UI in the PNG,
and save released the capture lease. Clipboard owner, preferences and user
sessions were unchanged. Copy/hidden-owner release, failure retention and stale
process recovery are covered by focused synthetic tests. This does not claim a
native accepted-copy test over the user's clipboard.

## Floating control interaction correction

A real-pointer regression reproduced the color dialog as an active modal window
stacked behind the unmanaged capture overlay. The visible toolbar still received
hit tests correctly, but the hidden modal blocked interaction. Color, text and
number editors are now embedded, nonmodal controls in the overlay. Escape closes
an open editor and returns to the capture; palette whitespace consumes input
instead of propagating a new region gesture. Color can also be chosen in object
selection mode. Save uses a visible nonblocking transient dialog above this
capture, preserving the document and lease when cancelled or when export fails.

Qt Spanish translations load locally from `qtbase_es.qm`, with a narrow fallback
for color labels. Screen sampling is explicitly hidden/disabled because it would
sample the dimmed overlay rather than the original frozen pixels. Palette and
HTML color selection remain available. No new keyboard shortcut or capture mode.

Runtime `a708faf` is installed as **e138e7af89c776c86d79** (52 manifest hashes).
Eight focused interaction/lease tests passed. Real-pointer installed verification
opened Color, typed an HTML color and applied it to an object; typed/applied text;
opened/cancelled number editing with Escape; checked control hit routing over a
large crop; cancelled then completed a visible/focused Save dialog with exact PNG
output. Copiar was clicked physically and dispatched once using an isolated copy
backend, without exercising or mutating the user's system clipboard. Clipboard
owner stayed unchanged and keyboard/pointer grabs were available. Evidence uses
only an owned opaque fixture. The old user session was preserved until it closed
naturally; installing this version did not replace its pinned release in place.
