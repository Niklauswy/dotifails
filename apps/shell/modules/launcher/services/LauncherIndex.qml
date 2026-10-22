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
import "Search.js" as Search

// In-memory indexes behind the launcher. Everything the root view filters per keystroke lives
// here as plain JS rows; slow sources (clipboard, files) are loaded asynchronously.
Singleton {
    id: root

    readonly property string home: Quickshell.env("HOME")
    readonly property int maxApps: Math.max(4, Math.min(GlobalConfig.launcher.maxShown, 12))

    // Commands
    readonly property var commands: Catalog.views().concat(Catalog.tools(Array.from(GlobalConfig.launcher.actions.values)))

    // Usage: pinned and recent items, persisted in the state dir
    property var pinned: []
    property var recent: []
    readonly property var pins: pinned.map(resolve).filter(Boolean)
    readonly property var recents: recent.map(resolve).filter(Boolean).slice(0, 6)

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

    // Streaming file search
    property var files: []
    property bool filesBusy
    property string wanted
    property string started
    property var pending: []

    readonly property var context: ({
            apps: Apps.rows, commands, clips, files, recentFiles, calcHistory, browse, places,
            pins, recents, maxApps
        })

    function snapshot(row: var): var {
        const out = {};
        for (const k of ["kind", "key", "title", "subtitle", "icon", "type", "path", "isDir", "l", "a"])
            if (row[k] !== undefined)
                out[k] = row[k];
        return out;
    }

    function resolve(item: var): var {
        if (item.key.startsWith("app:"))
            return Apps.rows.find(r => r.key === item.key) ?? null;
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

    function remember(row: var): void {
        if (row.kind !== "cmd" && row.kind !== "file")
            return;
        recent = [{key: row.key, row: snapshot(row)}].concat(recent.filter(r => r.key !== row.key)).slice(0, 20);
        save();
    }

    function save(): void {
        store.setText(JSON.stringify({pinned, recent}));
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

    function searchFiles(query: string): void {
        wanted = query.trim();
        if (!wanted) {
            files = [];
            pending = [];
            filesBusy = false;
            if (finder.running)
                finder.signal(15);
            return;
        }
        filesBusy = true;
        if (finder.running)
            finder.signal(15); // onExited starts the newest wanted query
        else
            startFinder();
    }

    function startFinder(): void {
        if (!wanted) {
            filesBusy = false;
            return;
        }
        started = wanted;
        files = [];
        pending = [];
        const prune = [];
        for (const n of [".*", "node_modules", "__pycache__", "venv", "go", "snap", "target", "build", "dist", "vendor", "Trash"])
            prune.push("-name", n, "-o");
        prune.pop();
        const names = [];
        for (const t of Search.terms(started))
            names.push("-iname", "*" + t.replace(/[\\*?\[\]]/g, "\\$&") + "*");
        finder.command = ["nice", "-n", "10", "find", home, "-maxdepth", "8", "(", ...prune, ")", "-prune", "-o", "(", "-type", "f", "-o", "-type", "d", ")", ...names, "-printf", "%y%p\\n"];
        finder.running = true;
    }

    function onFileLine(line: string): void {
        if (started !== wanted || line.length < 2)
            return;
        pending.push(Files.row(line.slice(1), line[0] === "d", home));
        if (pending.length >= 400)
            finder.signal(15);
        if (!flush.running)
            flush.start();
    }

    function publishFiles(): void {
        const ts = Search.terms(started);
        const scored = pending.map(r => ({r, s: Search.score(ts, r) - r.a.length * 0.2 - (r.isDir ? 0 : -30)}));
        scored.sort((x, y) => y.s - x.s);
        files = scored.slice(0, 40).map(x => x.r);
    }

    function decorateClips(rows: var): var {
        return rows.filter(r => r.kind === "clip").map(r => Object.assign(r, {
                key: "clip:" + r.id, type: r.clip_kind,
                l: (r.clip_kind === "image" ? "image screenshot picture" : r.value.slice(0, 400)).toLowerCase(), a: r.clip_kind
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
                root.recent = d.recent ?? [];
            } catch (e) {}
        }
    }

    Process {
        id: finder

        stdout: SplitParser {
            onRead: line => root.onFileLine(line)
        }
        onExited: {
            if (root.started !== root.wanted)
                root.startFinder();
            else {
                root.publishFiles();
                root.filesBusy = false;
            }
        }
    }

    Timer {
        id: flush

        interval: 45
        onTriggered: root.publishFiles()
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
