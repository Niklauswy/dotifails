// Wysun wallpaper library for the carousel: scans the wallpaper folders and
// generates/caches thumbnails in the background (`wysun wallpaper list|thumbs`).
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import qs.utils

Singleton {
    id: root

    // [{ path, name, animated, thumb }] sorted by name
    property var entries: []
    // path -> cached thumbnail file; replaced wholesale so bindings refresh
    property var thumbs: ({})
    property bool scanning: false
    property bool active: false
    // One reference per screen showing the picker; the worker lives while any is open.
    property int users: 0

    readonly property var directories: {
        const dirs = [Paths.wallsdir, `${Paths.wallsdir}/Animated`, `${Paths.home}/.local/share/backgrounds`];
        for (const folder of Wallpapers.wysunWallpaper.folders ?? [])
            dirs.push(folder);
        return dirs;
    }

    property var _queued: ({})
    property var _pending: []
    property bool _workerReady: false

    function thumbFor(path: string): string {
        return thumbs[path] ?? "";
    }

    function open(): void {
        users++;
        if (active)
            return;
        active = true;
        scanning = true;
        scan.running = false;
        scan.running = true;
        worker.running = true;
    }

    function close(): void {
        users = Math.max(0, users - 1);
        if (users > 0)
            return;
        active = false;
        _workerReady = false;
        worker.running = false;
        _pending = [];
        _queued = ({});
    }

    // Ask for a thumbnail; the worker serves requests in the order they arrive.
    function request(path: string): void {
        if (!active || thumbs[path] || _queued[path])
            return;
        _queued[path] = true;
        if (_workerReady)
            worker.write(`${path}\n`);
        else
            _pending.push(path);
    }

    Process {
        id: scan

        command: ["wysun", "wallpaper", "list", ...root.directories]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const list = JSON.parse(text);
                    const known = {};
                    for (const e of list)
                        if (e.thumb)
                            known[e.path] = e.thumb;
                    root.thumbs = Object.assign({}, root.thumbs, known);
                    root.entries = list;
                } catch (error) {
                    console.warn("Wysun: wallpaper scan failed:", error);
                }
                root.scanning = false;
            }
        }
    }

    Process {
        id: worker

        command: ["wysun", "wallpaper", "thumbs"]
        stdinEnabled: true
        onStarted: {
            root._workerReady = true;
            for (const path of root._pending)
                write(`${path}\n`);
            root._pending = [];
        }
        onExited: root._workerReady = false
        stdout: SplitParser {
            onRead: line => {
                const cut = line.indexOf("\t");
                if (cut < 0 || cut === line.length - 1)
                    return;
                const copy = Object.assign({}, root.thumbs);
                copy[line.slice(0, cut)] = line.slice(cut + 1);
                root.thumbs = copy;
            }
        }
    }
}
