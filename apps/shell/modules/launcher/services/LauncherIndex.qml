pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Wysun.Config
import qs.services
import qs.utils
import "Catalog.js" as Catalog
import "Files.js" as Files
import "Usage.js" as Usage

// In-memory indexes behind the launcher. Everything the root view filters per keystroke lives
// here as plain JS rows; slow sources (clipboard, files) are loaded asynchronously.
Singleton {
    id: root

    readonly property string home: Quickshell.env("HOME")
    readonly property int maxApps: Math.max(4, Math.min(GlobalConfig.launcher.maxShown, 12))

    // Commands
    readonly property var commands: Catalog.views().concat(Catalog.tools(Array.from(GlobalConfig.launcher.actions.values)))
    readonly property var settings: Catalog.settings()

    // Pinned items and what the launcher learned from use (Usage.js), persisted in the state dir.
    property var pinned: []
    property var usage: ({})
    property var picks: []
    readonly property var pins: pinned.map(resolve).filter(Boolean)

    // Loaded on demand
    property var clips: []
    property var recentFiles: []
    // Folder browsing (Files tab): the entries of `browsePath` and the usual places in home.
    property var browse: []
    property string browsePath
    property bool browseBusy
    property var places: []
    property var calcHistory: []
    property bool capturePaused

    // Recursive file search over the tree index written by launcher_data.py (see FileSearch.mjs),
    // in a worker thread. One search is in flight at a time; keys typed meanwhile collapse into the
    // latest query, sent when the worker answers.
    property var files: []
    property bool filesBusy: !indexReady
    property string wanted
    property string wantedScope
    property bool indexReady
    property bool searching
    property bool searchQueued
    readonly property int maxFileHits: 60

    readonly property var context: ({
            apps: Apps.rows, commands, settings, clips, files, recentFiles, calcHistory, browse, places,
            pins, usage, picks, maxApps
        })

    function snapshot(row: var): var {
        const out = {};
        for (const k of ["kind", "key", "title", "subtitle", "icon", "type", "path", "isDir", "editable", "l", "a"])
            if (row[k] !== undefined)
                out[k] = row[k];
        return out;
    }

    function resolve(item: var): var {
        if (item.key.startsWith("app:"))
            return Apps.rows.find(r => r.key === item.key) ?? null;
        if (item.key.startsWith("cmd:settings:"))
            return settings.find(r => r.key === item.key) ?? null;
        if (item.key.startsWith("cmd:"))
            return commands.find(r => r.key === item.key) ?? null;
        return item.row ?? null;
    }

    function isPinned(row: var): bool {
        return pinned.some(p => p.key === row.key) || (row.kind === "app" && GlobalConfig.launcher.favouriteApps.includes(row.id));
    }

    function togglePin(row: var): void {
        if (pinned.some(p => p.key === row.key))
            pinned = pinned.filter(p => p.key !== row.key);
        else
            pinned = pinned.concat([{key: row.key, row: snapshot(row)}]);
        save();
    }

    // Something was opened from the launcher after typing `query` ("" from the suggestions).
    function remember(row: var, query: string): void {
        if (!["app", "cmd", "file"].includes(row.kind))
            return;
        const next = Usage.record(usage, picks, row.key, query ?? "", Date.now(), row.kind === "file" ? snapshot(row) : null);
        usage = next.usage;
        picks = next.picks;
        save();
    }

    function save(): void {
        store.setText(JSON.stringify({pinned, usage, picks}));
    }

    // Async data sources -----------------------------------------------------------------------

    function refresh(): void {
        clipProc.running = false;
        clipProc.running = true;
    }

    // An open window of this app, if any (matched on the Wayland class).
    function windowOf(row: var): var {
        const keys = [row.startupClass, row.id.replace(/\.desktop$/, "")].filter(Boolean).map(k => k.toLowerCase());
        for (const t of Hypr.toplevels.values) {
            const cls = (t.lastIpcObject?.class ?? "").toLowerCase();
            if (cls && keys.includes(cls))
                return t.address;
        }
        return null;
    }

    function loadRecentFiles(): void {
        recentProc.running = false;
        recentProc.running = true;
    }

    // Lists one folder (hidden entries skipped; %Y follows symlinks so linked folders open too).
    function listDir(path: string): void {
        browsePath = path;
        browse = [];
        browseBusy = true;
        dirProc.running = false;
        dirProc.command = ["find", path, "-mindepth", "1", "-maxdepth", "1", "-not", "-name", ".*", "-printf", "%Y\t%p\n"];
        dirProc.running = true;
    }

    // Home plus the XDG folders that exist, in a familiar order.
    readonly property var placeNames: [["Desktop", "Escritorio"], ["Documents", "Documentos"], ["Downloads", "Descargas"],
        ["Pictures", "Imágenes"], ["Music", "Música"], ["Videos", "Vídeos"], ["Projects", "Proyectos"]]
    readonly property var placeIcons: ({Desktop: "desktop_windows", Escritorio: "desktop_windows", Documents: "description",
            Documentos: "description", Downloads: "download", Descargas: "download", Pictures: "image", "Imágenes": "image",
            Music: "music_note", "Música": "music_note", Videos: "movie", "Vídeos": "movie", Projects: "code", Proyectos: "code"})

    function loadPlaces(): void {
        placesProc.running = false;
        placesProc.command = ["find", home, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\n"];
        placesProc.running = true;
    }

    function placeRow(path: string, title: string, icon: string): var {
        return Object.assign(Files.row(path, true, home), {title, icon, type: "Place", key: "place:" + path});
    }

    function loadCalcHistory(): void {
        calcProc.running = false;
        calcProc.running = true;
    }

    // Tesseract pass over screenshots copied before the text was recognized; the list refreshes as each one finishes.
    function recognizePending(): void {
        ocrProc.running = true;
    }

    function loadStatus(): void {
        statusProc.running = false;
        statusProc.running = true;
    }

    function mutate(args: var): void {
        actProc.command = ["python3", "-I", LauncherData.script, "act", ...args];
        actProc.running = true;
    }

    function exportClip(id: int, callback: var): void {
        exportCallback = callback;
        exportProc.command = ["python3", "-I", LauncherData.script, "clip-file", String(id)];
        exportProc.running = true;
    }
    property var exportCallback: null

    // Keeps the index fresh: built on first use, refreshed in the background once it is a minute old.
    function ensureFileIndex(): void {
        treeProc.running = false;
        treeProc.running = true;
    }

    // `scope` limits the search to one folder (and all of its subfolders), relative to home or absolute.
    function searchFiles(query: string, scope: string): void {
        wanted = query.trim();
        wantedScope = scope ? scope.replace(home + "/", "").replace(/^\/+|\/+$/g, "") : "";
        if (scope === home)
            wantedScope = "";
        if (!wanted || !indexReady) {
            if (files.length)
                files = [];
            return;
        }
        if (searching)
            searchQueued = true;
        else
            postSearch();
    }

    function postSearch(): void {
        searching = true;
        searchQueued = false;
        fileWorker.sendMessage({q: wanted, scope: wantedScope, limit: maxFileHits});
    }

    function decorateClips(rows: var): var {
        return rows.filter(r => r.kind === "clip").map(r => Object.assign(r, {
                key: "clip:" + r.id, type: r.clip_kind,
                l: (r.clip_kind === "image" ? "image screenshot picture " + (r.ocr ?? "").replace(/\s+/g, " ") : r.value.slice(0, 400)).toLowerCase(), a: r.clip_kind
            }));
    }

    FileView {
        id: store

        path: `${Paths.state}/launcher.json`
        printErrors: false
        onLoaded: {
            try {
                const d = JSON.parse(text());
                root.pinned = d.pinned ?? [];
                root.picks = d.picks ?? [];
                // Older files only had a `recent` list: it seeds what the launcher has learned.
                root.usage = d.usage ?? Usage.fromRecent(d.recent ?? [], Date.now());
            } catch (e) {}
        }
    }

    FileView {
        id: treeFile

        path: `${root.home}/.local/share/orbit/launcher-files.idx`
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: fileWorker.sendMessage({index: text()})
    }

    WorkerScript {
        id: fileWorker

        source: "FileSearchWorker.mjs"
        onMessage: m => {
            if (m.ready) {
                // A search still in flight was sent after the new index, so it already uses it.
                root.indexReady = true;
                if (!root.searching && root.wanted)
                    root.postSearch();
                return;
            }
            root.searching = false;
            if (root.searchQueued) {
                root.postSearch();
                return;
            }
            if (m.q === root.wanted && m.scope === root.wantedScope)
                root.files = m.rows.map(r => Files.row(root.home + "/" + r[0], r[1], root.home));
        }
    }

    Process {
        id: treeProc

        command: ["python3", "-I", LauncherData.script, "files-index"]
        onExited: if (!root.indexReady) treeFile.reload()
    }

    Process {
        id: ocrProc

        command: ["python3", "-I", LauncherData.script, "act", "ocr-pending"]
        stdout: SplitParser {
            onRead: ocrRefresh.restart()
        }
    }

    Timer {
        id: ocrRefresh

        interval: 400
        onTriggered: root.refresh()
    }

    Process {
        id: clipProc

        command: ["python3", "-I", LauncherData.script, "query", "clip", ""]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.clips = root.decorateClips(JSON.parse(text)); } catch (e) { root.clips = []; }
            }
        }
    }

    Process {
        id: dirProc

        stdout: StdioCollector {
            onStreamFinished: {
                const rows = [];
                for (const line of text.split("\n")) {
                    const tab = line.indexOf("\t");
                    if (tab > 0)
                        rows.push(Files.row(line.slice(tab + 1), line.slice(0, tab) === "d", root.home));
                }
                rows.sort((a, b) => (b.isDir - a.isDir) || a.l.localeCompare(b.l));
                root.browse = rows.slice(0, 800);
                root.browseBusy = false;
            }
        }
    }

    Process {
        id: placesProc

        stdout: StdioCollector {
            onStreamFinished: {
                const present = text.split("\n");
                const rows = [root.placeRow(root.home, "Home", "home")];
                for (const pair of root.placeNames) {
                    const name = pair.find(n => present.includes(n));
                    if (name)
                        rows.push(root.placeRow(root.home + "/" + name, name, root.placeIcons[name] ?? "folder"));
                }
                root.places = rows;
            }
        }
    }

    Process {
        id: recentProc

        command: ["python3", "-I", LauncherData.script, "query", "files", ""]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.recentFiles = JSON.parse(text).filter(r => r.kind === "file").map(r => Files.row(r.path, false, root.home)); } catch (e) { root.recentFiles = []; }
            }
        }
    }

    Process {
        id: calcProc

        command: ["python3", "-I", LauncherData.script, "query", "calc", ""]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.calcHistory = JSON.parse(text).map(r => ({kind: "history", key: "calc:" + r.query, title: r.value, subtitle: r.query, icon: "history", type: "Calculator", value: r.value, expression: r.query, l: (r.query + " " + r.value).toLowerCase(), a: ""}));
                } catch (e) { root.calcHistory = []; }
            }
        }
    }

    Process {
        id: statusProc

        command: ["python3", "-I", LauncherData.script, "query", "status", ""]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.capturePaused = !!JSON.parse(text)[0].paused; } catch (e) {}
            }
        }
    }

    Process {
        id: actProc

        onExited: {
            clipProc.running = true;
            root.loadStatus();
        }
    }

    Process {
        id: exportProc

        stdout: StdioCollector {
            onStreamFinished: {
                const path = text.trim();
                if (path && root.exportCallback)
                    root.exportCallback(path);
            }
        }
    }
}
