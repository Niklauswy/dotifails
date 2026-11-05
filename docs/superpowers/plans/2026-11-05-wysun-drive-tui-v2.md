# Wysun Drive selector v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** the layout-B selector of the spec, on a transparent background.
**Spec:** `docs/superpowers/specs/2026-11-05-wysun-drive-tui-v2-design.md`
**Architecture:** engine option for transparency; CLI gains `--resultado`, `--origen`, deferred notify;
the TUI becomes `ui/app.py` (state, keys, child process) + `ui/view.py` (drawing) + `ui/preview.py`
(icons, previews, quota) and runs uploads as a child process.

## Global Constraints
- stdlib only; ffmpeg optional. Colours from `Palette` only (preview pixels are content).
- The app password never reaches argv, the screen, status or result files.
- Existing CLI contract (`up --json`, exit codes) unchanged.

## Review Focus
- Terminal narrower than 100 columns: Detail pane hidden, nothing overlaps.
- File without read permission / broken image: preview says so, no crash.
- Child process dies (killed): TUI shows the error, does not hang.
- Leaving with `q` while uploading: upload continues, notification arrives.
- Wallpaper/mode change while open: palette reloads, preview pixels unchanged.

### Task 1: engine transparency
Files: `wysun_core/tui/screen.py` (`render(prev, cur, transparent_bg=None)`), `app.py` (`App(..., transparent=False)`), test `tests/test_tui_engine*` or new `tests/test_tui_transparent.py`.
- [ ] Test: with `transparent_bg=canvas.bg` no `48;2;` for blank cells, painted cells keep theirs.
- [ ] Implement; pass; commit.

### Task 2: CLI/API additions
`client.quota() -> (used, available|None)`, `api.remove_link(remote)`, `history` `source` field,
`up --resultado FILE --origen NAME`, SIGUSR1 → notify at the end. Files/screenshot pass `--origen`.
- [ ] Tests in `tests/drive/`; implement; commit.

### Task 3: TUI v2
`ui/preview.py`, `ui/view.py`, `ui/app.py` rewritten; tests `tests/drive/test_tui.py` updated
(browse, mark/chips, upload via child against fake server, background `b`, Recientes `k`/`n`,
narrow terminal, login panels kept).
- [ ] Implement; pass; commit.

### Task 4: Ghostty + docs + deploy
`config/.config/ghostty/config` `background-opacity-cells = true`; docs/utilities.md; full suites; `wysun update`.
