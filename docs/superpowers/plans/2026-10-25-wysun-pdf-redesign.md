# Wysun PDF redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continuous, virtualized, zoomable PDF reader with links, search highlighting, two-page view and per-document memory, rebuilt on the shared `wysun_core.ui` kit.

**Architecture:** The MuPDF process (`pdf_engine.py`) keeps exclusive ownership of the document. It replies with JSON headers plus raw binary frames. `pdf_worker.py` adds priority, keys and cancellation. Pure modules (`pdf_layout`, `pdf_cache`, `pdf_state`) hold geometry, the bounded cache and persistence. `pdf_source` bridges them to Qt, `pdf_view` paints only the visible rows, and `pdf_window`/`pdf_chrome`/`pdf_sidebar` compose the UI from kit widgets. `pdf_material.py` is deleted.

**Tech Stack:** Python 3.13, PySide6 6.8, PyMuPDF 1.26.7 (venv `/tmp/wysun-pdf-venv`), unittest.

**Spec:** `docs/superpowers/specs/2026-10-25-wysun-pdf-redesign-design.md`

## Global Constraints

- Touch only `apps/wysun/pdf_*.py`, `tests/pdf/`, `tests/test_pdf_theme.py`, `docs/pdf-reader.md`, `config/.local/share/applications/wysun-pdf.desktop`, docs/superpowers files.
- Colours only via `wysun_core.qt_theme.color()`; literals only with `# theme-exception: motivo`. Sizes via `wysun_core.ui.style.metric()`/`text_font()`/`tokens()`.
- Raster limit per image: 8 000 000 px and 2800 px width. Render cache: 192 MiB, ≤ 2 widths per page. Info cache: 96 pages. Thumbnails: 48 × ≤ 120 px wide.
- Zoom: 100 % = 4/3 px per PDF point; range 0.10–8.00; Ctrl+wheel factor 1.1 per notch; render debounce 120 ms; prefetch margin = ½ viewport height.
- Private state: `paths.state('wysun', 'pdf-reader', 'positions.json')` (0600, ≤ 200 entries, SHA-256 keys); prefs `paths.config('wysun', 'pdf-reader.json')`.
- External links: only `http`, `https`, `mailto`, after confirmation, `xdg-open` with the original environment.
- Tests: `HOME/XDG_*` temporary; `QT_QPA_PLATFORM=offscreen`; `/tmp/wysun-pdf-venv/bin/python -m unittest discover -s tests/pdf`; `python3 -m unittest discover -s tests`.
- Atomic writes and XDG lookups only through `wysun_core` (`tests/test_core_owns_io.py`).

## Review Focus

- Rotated pages (90/270): words, links and hits must line up with the displayed page — test in Task 1 (links on rotated page) and Task 6 (selection on rotated page reused from existing test).
- Edit while a render for that page is in flight: stale raster must not overwrite the edited one — Task 4 test `test_edit_revision_discards_inflight_render`.
- Reopening a document whose page count shrank since the remembered position — Task 3 test `test_restore_clamps_to_page_count`.
- Search text changed while a search runs: old hits must not mix in — Task 8 test `test_new_query_discards_old_hits`.
- Engine crash mid-session: UI disables actions and reports, no hang — kept in Task 2 (`failed` signal) and asserted in Task 8 workflow (`worker_failed`).

---

### Task 1: Engine protocol (sizes, binary rasters, page_info, search context, annotations)

**Files:**
- Create: `apps/wysun/pdf_layout.py` (only `raster_width` for now; extended in Task 3)
- Modify: `apps/wysun/pdf_engine.py`
- Test: `tests/pdf/test_engine.py`

**Interfaces:**
- Produces: `pdf_layout.raster_width(page_w: float, page_h: float, want: int) -> int` (min of want, 2800, sqrt(8e6/(w·h))·w; ≥ 1).
- Engine ops (each returns dict; a `bytes` blob travels as `result['_blob']` in-process, framed by `main()`):
  `open(path, password='') -> {path, pages, outline, editable, sizes: [[w,h],...]}`;
  `render(page, width) -> {page, width, height, stride, _blob}` (RGB888);
  `thumbnail(page) -> {page, width, height, stride, _blob}`;
  `page_info(page) -> {page, words: [[x0,y0,x1,y1,text,block,line],...], links: [{rect, page, y} | {rect, uri}], annotations: [{xref,type,text,rect}]}`;
  `search(page, text) -> {page, hits: [[x0,y0,x1,y1]], contexts: [str]}`;
  `annotations() -> {items: [{page,xref,type,text}]}`.
- `main()` framing: writes `json.dumps({'result': header, 'blob': n})+'\n'` then `n` raw bytes when `_blob` is present.

- [ ] Step 1: tests — `test_open_reports_rotated_sizes` (portrait page rotated 90 → `[h, w]`), `test_render_is_raw_rgb` (`len(_blob) == stride*height`, `width <= raster_width`), `test_page_info_words_and_links` (insert `page.insert_link({'kind': fitz.LINK_GOTO, 'page': 2, 'from': rect, 'to': fitz.Point(0, 100)})` and a `LINK_URI` `https://example.org`; assert one internal with `page == 2`, one external with `uri`), `test_search_returns_context` (context contains the matched word and is ≤ 120 chars), `test_annotations_lists_whole_document`, and the existing tests adapted (`render(...)['words']` → `page_info`).
- [ ] Step 2: run, expect failures (`KeyError sizes`, `AttributeError page_info`).
- [ ] Step 3: implement. Links: `p.get_links()`, rect `fitz.Rect(l['from']) * p.rotation_matrix`; internal `y = (fitz.Point(l['to']) * doc[l['page']].rotation_matrix).y` when present. Context: the words of the hit's `(block, line)` joined, trimmed to 120 chars around the term.
- [ ] Step 4: run `tests/pdf/test_engine.py`, expect OK.
- [ ] Step 5: commit `feat(pdf): engine sends raw rasters, page sizes, links and search context`.

### Task 2: Worker transport (frames, priority, keys, cancellation)

**Files:** Modify `apps/wysun/pdf_worker.py`; Test `tests/pdf/test_worker.py`.

**Interfaces:**
- `PdfWorker.request(op, callback, *, priority=0, key=None, **args)`; callback receives `{'result': dict}` with `result['blob']: bytes` when framed, or `{'error': str}`.
- `PdfWorker.cancel(predicate: Callable[[op, key], bool]) -> int` (removed count; callbacks of removed items are not called).
- `PdfWorker.queued_keys() -> set`; `failed` signal unchanged; `stop()` unchanged.

- [ ] Step 1: tests with the real engine — `test_binary_frame_roundtrip` (render returns `bytes` of `stride*height`), `test_priority_runs_interactive_first` (queue thumbnail(p=1), search(p=2), render(p=0) while `open` is active; completion order render, thumbnail, search), `test_same_key_replaces_queued`, `test_cancel_drops_queued_renders`.
- [ ] Step 2: run, expect failures.
- [ ] Step 3: implement: stable insert by priority; two-phase read (line, then `blob` bytes).
- [ ] Step 4: run, expect OK. Step 5: commit `feat(pdf): prioritised, cancellable worker with binary frames`.

### Task 3: Pure geometry, cache and state

**Files:** Extend `apps/wysun/pdf_layout.py`; create `apps/wysun/pdf_cache.py`, `apps/wysun/pdf_state.py`; tests `tests/pdf/test_layout.py`, `test_cache.py`, `test_state.py` (no fitz, no Qt).

**Interfaces:**
- `ZOOM_MIN = .1`, `ZOOM_MAX = 8.0`, `PX_PER_PT = 4/3`.
- `Layout(sizes, zoom, mode='single'|'spread', viewport_width, gap, margin)`; attrs `rects: list[(x,y,w,h)]`, `width`, `height`, `rows: list[list[int]]`; methods `visible(top, bottom) -> list[int]`, `page_at(x, y) -> int|None`, `row_of(page) -> int`.
- `fit_width(sizes, mode, viewport_width, gap, margin) -> float`; `fit_page(sizes, mode, page, viewport_width, viewport_height, gap, margin) -> float`.
- `anchor(layout, x, y) -> (page, fx, fy)` and `locate(layout, anchor) -> (x, y)` (content coords).
- `RenderCache(budget=192*2**20, per_page=2)`: `put(page, width, image, nbytes)`, `get(page, width)`, `best(page, width)`, `drop(page)`, `clear()`, `bytes`.
- `pdf_state.Positions()`: `load(path) -> dict|None`, `save(path, state: dict)`; `Preferences()`: `get(key, default)`, `set(**values)` preserving unknown keys.

- [ ] Step 1: tests — single stacking (`rects[1].y == rects[0].y + h0 + gap`), spread pairing (`rows == [[0,1],[2,3],[4]]`), `visible` only intersecting rows (60 pages, window over page 30 → `{29,30}`-ish set, never 0), `fit_width` makes widest row fill `viewport - 2*margin`, anchor round-trip after zoom change (same `(page,fx,fy)` maps to new coords; error < 1 px), cache evicts LRU over budget and keeps ≤ 2 widths per page, `best` returns nearest width, positions: 0600 file, SHA keys (no path text in file), cap 200, `test_restore_clamps_to_page_count` (load clamps via `clamp(state, pages)` helper → `pdf_state.clamp(state, pages) -> dict`), preferences keep unknown keys.
- [ ] Step 2: run, fail. Step 3: implement. Step 4: run, OK. Step 5: commit `feat(pdf): pure layout, bounded raster cache and per-document memory`.

### Task 4: PageSource (virtualized requests)

**Files:** Create `apps/wysun/pdf_source.py`; test `tests/pdf/test_source.py` (fake worker, Qt core only).

**Interfaces:**
- `PageSource(worker)`, signals `changed(int page)`, `info_ready(int page)`.
- `reset(generation_sizes: list)`; `want(requests: list[(page, width_px)])` — cancels queued `('render', key)` not in requests, enqueues missing renders (key `('render', page)`), enqueues `page_info` for each page in requests not cached (key `('info', page)`); `image(page, width) -> QImage|None` (exact or best); `info(page) -> dict|None`; `invalidate(page)` (bumps revision, drops caches); `requested: list[(page,width)]` log for tests.
- [ ] Step 1: tests — `test_want_cancels_stale_renders`, `test_edit_revision_discards_inflight_render`, `test_image_falls_back_to_nearest_width`.
- [ ] Steps 2–5 as usual; commit `feat(pdf): page source with cancellation and revisions`.

### Task 5: Theme layer

**Files:** Create `apps/wysun/pdf_theme.py`; rewrite `tests/test_pdf_theme.py`.

**Interfaces:** `ReaderMode(prefs: pdf_state.Preferences)`: `.pinned -> 'light'|'dark'|None`, `.mode`, `set(mode|None)` (persists, applies), `apply()`; `SYMBOLS: tuple[str]` every Material glyph the reader paints.
- [ ] Step 1: tests — following desktop (`WYSUN_THEME` unset → env untouched), pinning opposite sets env and `qt_theme.tokens()['mode']` flips, pinning same mode leaves env original, `set(None)` restores, persistence in `pdf-reader.json`, every name in `SYMBOLS` is `ligature_available`.
- [ ] Steps 2–5; commit `refactor(pdf): reader mode is a thin layer over qt_theme`.

### Task 6: DocumentView

**Files:** Create `apps/wysun/pdf_view.py`; test `tests/pdf/test_view.py` (fake source with solid images; no fitz).

**Interfaces:** `DocumentView(source)`: `set_document(sizes)`, `set_zoom(value, anchor=None)`, `zoom_mode` (`'width'|'page'|'custom'`), `set_fit(kind)`, `zoom_by(factor, viewport_point=None)`, `set_mode('single'|'spread')`, `go(page, y=None)`, `current_page()`, `position() -> dict`, `restore(dict)`, `set_hits(dict[page,list], current=(page, i)|None)`, `selection -> (page, [indices])`, `selected_text()`, `clear_selection()`, `selection_rect() -> QRect` (viewport); signals `pageChanged(int)`, `zoomChanged(float)`, `selectionChanged()`, `selectionFinished()`, `linkActivated(dict)`, `noteRequested(int, QPointF)`; `note_mode` bool.
- [ ] Step 1: tests — `test_only_visible_pages_are_requested` (60 pages; after `go(30)` every requested page within visible±margin), `test_ctrl_wheel_keeps_point_under_cursor` (anchor error < 2 px), `test_spread_places_pairs_side_by_side`, `test_fit_width_tracks_resize`, `test_drag_selects_across_lines`, `test_click_on_link_emits`.
- [ ] Steps 2–5; commit `feat(pdf): continuous virtualized document view`.

### Task 7: Chrome & sidebar widgets

**Files:** Create `apps/wysun/pdf_chrome.py`, `apps/wysun/pdf_sidebar.py`; extend `tests/test_pdf_theme.py` with offscreen construction checks (no fitz).

**Interfaces:** `ToolGroup(*buttons)`, `ZoomControl` (signals `zoom_in`, `zoom_out`, `fit(str)`, `percent(float)`; `set_zoom(float, mode)`), `ViewModeSwitch` (signal `changed(str)`; `set_mode`), `PageIndicator` (signal `jump(int)`; `set_page(cur, total)`), `SelectionBar` (signals `action(str)`; `set_editable(bool)`, `place(QRect)`), `Emblem`, `NoteDialog(parent, text='', title=...)` with `.editor`, `INKS`. `Sidebar`: `tab(int)`, `pages_view`/`page_model`, `outline` (QListWidget), `notes` (QListWidget), `results` (QListWidget), `delete_button`, signals `page_requested(int)`, `hit_requested(int)`, `note_activated(dict)`, `delete_requested(dict)`, `thumbnails_wanted(list)`.
- [ ] Step 1: tests — widgets build in light & dark, every control has an accessible name, no stylesheet contains `@`.
- [ ] Steps 2–5; commit `feat(pdf): reader chrome and tabbed sidebar on the shared kit`.

### Task 8: Window integration, remove pdf_material, docs

**Files:** Rewrite `apps/wysun/pdf_window.py`; delete `apps/wysun/pdf_material.py`; adjust `apps/wysun/pdf_app.py`; rewrite `tests/pdf/test_window.py`; update `docs/pdf-reader.md`, `.desktop` (Actions? no — keep, add `Keywords`).

- [ ] Step 1: tests with real engine — workflow (open, highlight, save, reopen annotations), `test_virtualization_in_window`, `test_search_highlights_and_enter_navigates`, `test_new_query_discards_old_hits`, `test_internal_and_external_links` (patch `window.confirm_link` → True and `window.launch_url`), `test_spread_mode_and_zoom`, `test_position_is_remembered`, screenshots when `WYSUN_PDF_SCREENSHOTS`.
- [ ] Step 2–4; full suites; Step 5: commit `feat(pdf): redesigned reader window`.

### Task 9: Screenshots, review, rebase

- [ ] Generate light/dark shots + two synthetic wallpaper schemes into `docs/superpowers/specs/pdf-shots/`.
- [ ] Fresh reviewer (`superpowers:requesting-code-review`), fix Critical/Important.
- [ ] Rebase on `main`, adopt renamed tokens if plan 03 landed, rerun all suites.
