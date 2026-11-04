# Wysun Music online Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Music in a tiled window, songs that stream from YouTube when they are not on disk (search, Home shelves,
Spotify lists), local first, like/playlist ⇒ download, and a redesigned «Añadir música» (selection, batches, no
«Revisar versión»).

**Architecture:** `Library` gains an in-memory *catalog* of non-local tracks (Spotify embed / YouTube rows) and an
`online` flag; `listenable(key)` replaces `available(key)` wherever playback filters. A `StreamResolver`
(`wysun_music/stream.py`, QThreadPool) turns a track into a YouTube watch URL (`data.find_video`, cached on disk) and
an audio URL (`yt-dlp -f bestaudio -g`, memory only, ~1 h), which `Player._load` hands to mpv. `online.py` reads the
public Spotify editorial playlists and YouTube mixes through `Metadata.request` (disk cache, ~20 h) and ranks «Para ti»
with a pure function. The download worker drops `review`, tags tracks with a batch token, and supports cancel.

**Tech Stack:** Python 3.13, PySide6 (qml-runtime venv), QML (`WysunM3`), mpv JSON IPC, yt-dlp.

**Spec:** `docs/superpowers/specs/2026-11-04-wysun-music-online-design.md`

## Global Constraints

- No literal colours/radii/spacing in QML: theme tokens only (`tests/test_theme_literals.py`).
- Credentials, cookies, accounts: none. Only public Spotify embed pages and yt-dlp.
- Audio is never written to disk while streaming; audio URLs are never persisted.
- `build(test=True)` (network off) must behave exactly like today: no online shelves, no YouTube search, no resolver.
- Private data stays under `WYSUN_MUSIC_HOME` (`~/.local/share/wysun/music`).
- Deploy with `wysun update`; do not edit `~/.local/share/wysun/app/`.

## Review Focus

1. Offline (or yt-dlp missing): every online path fails quietly; the queue skips streamed songs and keeps local ones.
2. A streamed song that is downloaded later keeps its key, favourite and history (no duplicate in the library).
3. Rapid next/next/next while resolving: only the last requested song starts (stale resolutions are dropped).
4. Restoring a session whose current song was streamed: does not crash; shows it paused (resolves on play).
5. Old `library.json` with `review` tracks: shown as ready (file present) or «No encontrada».

---

### Task 1: Tiled window

**Files:** Modify `config/.config/wysun/hyprland.lua:24` (class match becomes `^(wysun-recorder)$`).

- [ ] Edit the rule; `python3 -m unittest tests.test_installer* -q` style checks that grep hyprland.lua still pass.
- [ ] Commit.

### Task 2: Download worker without «review», batches, cancel, chosen version

**Files:** Modify `apps/python/wysun_music/data.py`; Test `tests/test_music_downloads.py`.

**Produces:**
- Statuses: `pending | downloading | ready | error | missing` (`review` gone; `missing` = «No encontrada»).
- `enqueue(manifest)` stamps every *newly queued* track with `batch=<collection id>:<int(time)>` and
  `batch_title=<collection title>`.
- `migrate(state) -> bool` (called inside `read_state` users via `worker()` and `retry_failed`): `review` →
  `ready` if `path` is a file else `missing`.
- `batches(state) -> list[dict(id,title,total,done,failed,active,progress)]` only for batches with unfinished tracks.
- `cancel_batch(token)`: drops `pending`/`missing`/`error` tracks of the batch (and from collections); a
  `downloading` one gets `cancel=True`, which `download_track`'s progress loop honours by killing yt-dlp and removing
  the partial file.
- `use_version(key, youtube_url)`: sets the url, `status='pending'`, clears error.
- `retry_failed()` retries `error` and `missing`.
- Duration mismatch ⇒ `ready` (no review); no match ⇒ `missing` with error «No se encontró una versión que coincida».

- [ ] Tests: migrate review→ready/missing; enqueue batch token/title only on new tracks; batches() counts; cancel
  removes pending and flags downloading; use_version requeues; retry includes missing.
- [ ] Implement; tests pass; commit.

### Task 3: Stream resolver

**Files:** Create `apps/python/wysun_music/stream.py`; Test `tests/test_music_stream.py`.

**Produces:**
- `audio_url(video_url) -> str` (`ytdlp() + ['-f','bestaudio/best','-g','--no-playlist','--',url]`, timeout 60 s).
- `entry_track(entry) -> dict` YouTube flat entry → `{id:'yt-'+id, title, artist, duration, youtube_url}`; splits
  «Artist - Title» when the channel is not a «- Topic» channel name and the title contains ` - `.
- `class StreamResolver(QObject)`: `resolved(str key, str url)`, `failed(str key, str message)`;
  `request(key, track)`; `cached(key) -> str|None` (audio URL younger than 50 min). Video URL lookups are cached in
  `Metadata` kind `stream-video` (30 d); audio URLs only in memory.

- [ ] Tests (fake ytdlp via patch): audio_url returns first line; entry_track splits; resolver emits resolved for a
  track with youtube_url, failed when find_video returns None.
- [ ] Implement; tests pass; commit.

### Task 4: Library catalog and online flag

**Files:** Modify `apps/python/wysun_music/library.py`; Test `tests/test_music_catalog.py`.

**Produces:** `Library.online: bool` (+ `online_changed`), `register(tracks)`, `known(key)`, `listenable(key)`,
`local(key)` (= `available`), `set_online_collections(list[dict(id,title,source,cover_url,tracks)])` → collection ids
`online:<id>` with kind `online`; `raw_collection(key)` (for covers); favourites and user playlists keep keys that are
`known`; `toggle_favorite`/`add_to_playlist`/`create_playlist` call `ensure_downloaded(keys)` for non-local known keys,
which enqueues them into collection `personal` («Tus descargas», append).

- [ ] Tests: register + listenable depends on online; favourite of a catalog key enqueues it and stays in Tus me gusta;
  local key wins (listenable even offline); online collection resolves.
- [ ] Implement; commit.

### Task 5: Player plays streams

**Files:** Modify `apps/python/wysun_music/player.py`, `apps/python/wysun_music/app.py`; Test `tests/test_music_streaming.py`.

**Produces:** `Player(library, persist, resolver=None)`; filters use `library.listenable`; `_load` for non-local keys
asks the resolver (token = key + serial; stale answers ignored), sets `buffering` (exposed as `Player.buffering`);
on `failed` skips forward when the load was automatic or the queue has more, else emits the message; prefetches the next
upcoming non-local key after each track change. `build()` creates the resolver only when `network`.

- [ ] Tests with a fake engine and fake resolver: stream key loads the resolved URL; stale resolution ignored; failure
  skips to the next local song; offline play of a stream key is filtered out.
- [ ] Implement; commit.

### Task 6: Online shelves and «Para ti»

**Files:** Create `apps/python/wysun_music/online.py`; Test `tests/test_music_online.py`.

**Produces:** `CHARTS` (ordered `(id, title, spotify playlist id)`: novedades New Music Friday
`37i9dQZF1DX4JAvHpjipBk`, top-mexico `37i9dQZEVXbO3qyFxbkOE1`, top-global `37i9dQZEVXbMDoHDwVN2tF`, exitos Today's Top
Hits `37i9dQZF1DXcBWIGoYBM5M`, pop Pop Rising `37i9dQZF1DWUa8ZRTfalHk`, latino Viva Latino `37i9dQZF1DX10zKzsJ2jva`,
reggaeton Baila Reggaeton `37i9dQZF1DWY7IeIP1cdjF`, rap RapCaviar `37i9dQZF1DX0XUsuxWHRQd`, rock Rock Classics
`37i9dQZF1DWXRqgorJj26U`, lofi `37i9dQZF1DWWQRwui0ExPn`); Spotify publishes no viral list in its embed (checked
2026-11-04), so «Virales» is dropped. `recommend(charts, artist_weights, local_keys, recent_keys, limit=30) -> keys`;
`class Online(QObject)` (`changed`): `refresh()` requests every chart (`Metadata` kind `online-chart`, ttl 20 h) and up
to 3 mixes (`online-mix`, `--playlist-end 25`) seeded from the most played songs with a `youtube_url`; registers
tracks in the library catalog; exposes `collections`, `for_you` (keys) and `mixes`.

- [ ] Tests: recommend ranks cross-chart and known artists first, excludes local and recent, caps per artist (≤2).
- [ ] Implement; commit.

### Task 7: Home, Search and the cloud mark

**Files:** Modify `quick/controller.py`, `quick/models.py` (role `local`), `pages/HomePage.qml`, `pages/SearchPage.qml`,
`parts/TrackRow.qml`, `parts/MusicCard.qml` (optional cloud), `pages/CollectionPage.qml` (download button on `online:`
collections → `addMusic.preview(collection id)`); tests in `tests/qml/check_music_pages.py`.

- Home: «Para ti» track shelf, mixes, then chart shelves (CollectionCard), only while `library.online`.
- Search: «En YouTube» list under library results (`addMusic`-independent; controller runs yt-dlp `ytsearch8`
  600 ms after the last change, only online; results registered in the catalog).
- [ ] Implement; QML checks pass in offscreen; commit.

### Task 8: «Añadir música» redesign

**Files:** Modify `quick/addmusic.py`, `pages/AddMusicPage.qml`; Test `tests/qml/check_music_addmusic.py`.

- Link ⇒ preview card (cover, title, count) + checklist; «Todas», «Solo las que no tengo», «Ninguna»;
  «Escuchar» and «Descargar N». Owned songs show «En tu biblioteca» and start unchecked under «Solo las que no tengo».
- YouTube search rows: click plays (stream), checkbox selects; «Descargar N».
- Batches section (`data.batches`), pause/continue, cancel per batch, collapsed «N no se pudieron descargar ·
  Reintentar» with an expandable list, each «Elegir otra versión» (search, pick, `data.use_version`).
- Import files/folder/open folder as a quiet secondary row at the bottom.
- [ ] Update checks; implement; commit.

### Task 9: Verify and deploy

- [ ] All suites in AGENTS.md (serially); MPRIS shows streamed song metadata; `wysun update`, `wysun reload`; open the
  real window and check it tiles, Home shelves, search, streaming and Añadir música in light and dark.
