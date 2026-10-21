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
    readonly property var session: ({
            logout: Array.from(GlobalConfig.session.commands.logout),
            hibernate: Array.from(GlobalConfig.session.commands.hibernate),
            reboot: Array.from(GlobalConfig.session.commands.reboot),
            shutdown: Array.from(GlobalConfig.session.commands.shutdown)
        })
    readonly property var systemCommands: Catalog.system(session)
    readonly property var commands: Catalog.views().concat(systemCommands, Catalog.tools(Array.from(GlobalConfig.launcher.actions.values), session))

    // Usage: pinned and recent items, persisted in the state dir
    property var pinned: []
    property var recent: []
    readonly property var pins: pinned.map(resolve).filter(Boolean)
    readonly property var recents: recent.map(resolve).filter(Boolean).slice(0, 6)

    // Loaded on demand
    property var clips: []
    property var snippets: []
    property var recentFiles: []
    property var calcHistory: []
    property var windows: []
    property bool capturePaused

    // Streaming file search
    property var files: []
    property bool filesBusy
    property string wanted
    property string started
    property var pending: []

    readonly property var context: ({
            apps: Apps.rows, commands, systemCommands, windows, clips, snippets, files, recentFiles, calcHistory,
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
        refreshWindows();
        clipProc.running = false;
        clipProc.running = true;
        snippetProc.running = false;
        snippetProc.running = true;
    }

    function refreshWindows(): void {
        const out = [];
        for (const t of Hypr.toplevels.values) {
            const ipc = t.lastIpcObject;
            const cls = ipc?.class ?? "";
            if (!t.title && !cls)
                continue;
            const title = t.title || cls;
            const entry = cls ? DesktopEntries.heuristicLookup(cls) : null;
            out.push({
                kind: "window", key: "win:" + t.address, address: t.address, title,
                subtitle: (entry?.name || cls) + (ipc?.workspace ? " · Workspace " + ipc.workspace.name : ""),
                icon: entry?.icon || cls.toLowerCase(), type: "Window", l: title.toLowerCase(), a: cls.toLowerCase()
            });
        }
        windows = out;
    }

    function loadRecentFiles(): void {
        recentProc.running = false;
        recentProc.running = true;
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
        id: snippetProc

        command: ["python3", "-I", LauncherData.script, "query", "snippets", ""]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.snippets = JSON.parse(text).filter(r => r.kind === "snippet").map(r => Object.assign(r, {key: "snippet:" + r.id, type: "Snippet", l: (r.title + " " + r.shortcut).toLowerCase(), a: r.body.toLowerCase().slice(0, 400)}));
                } catch (e) { root.snippets = []; }
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
            snippetProc.running = true;
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
