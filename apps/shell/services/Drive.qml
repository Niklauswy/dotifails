pragma Singleton

import QtQuick
import Qt.labs.folderlistmodel
import Quickshell
import Quickshell.Io
import "DriveLogic.js" as Logic

// Uploads of Wysun Drive in progress, read from the status files each one keeps in
// $XDG_RUNTIME_DIR/wysun-drive/<pid>.json (apps/python/wysun_drive/status.py). The bar shows
// and cancels them; uploads start from a terminal, Files or the screenshot tool. A file without
// a heartbeat for 30 s belongs to a process that is gone and is ignored.
Singleton {
    id: root

    readonly property string dir: `${Quickshell.env("XDG_RUNTIME_DIR")}/wysun-drive`
    property var files: ({})
    property real now: Date.now() / 1000
    readonly property var uploads: Logic.live(Object.values(files), now)
    readonly property bool active: uploads.length > 0
    readonly property real progress: Logic.overall(uploads)

    function cancel(pid: int): void {
        Quickshell.execDetached(["wysun", "drive", "--detener", String(pid)]);
    }

    function open(): void {
        Quickshell.execDetached(["wysun", "drive", "--terminal"]);
    }

    function put(name: string, text: string): void {
        if (!/^\d+\.json$/.test(name))
            return;
        try {
            const next = Object.assign({}, files);
            next[name] = JSON.parse(text);
            files = next;
        } catch (error) {
            // Never half-written (atomic), but a foreign file must not break the bar.
        }
    }

    function drop(name: string): void {
        if (!(name in files))
            return;
        const next = Object.assign({}, files);
        delete next[name];
        files = next;
    }

    // The directory must exist for the folder model to watch it.
    Process {
        running: true
        command: ["mkdir", "-p", "-m", "0700", root.dir]
        onExited: folder.folder = "file://" + root.dir
    }

    FolderListModel {
        id: folder

        nameFilters: ["*.json"]
        showDirs: false
        showHidden: false
        sortField: FolderListModel.Name
    }

    Instantiator {
        id: readers

        model: folder

        FileView {
            required property string fileName
            required property string filePath

            path: filePath
            printErrors: false
            watchChanges: true
            onFileChanged: reload()
            onLoaded: root.put(fileName, text())
            Component.onDestruction: root.drop(fileName)
        }
    }

    // Progress and heartbeat: re-read while something uploads (atomic writes replace the file).
    Timer {
        interval: 1000
        repeat: true
        running: folder.count > 0
        triggeredOnStart: true
        onTriggered: {
            root.now = Date.now() / 1000;
            for (let i = 0; i < readers.count; i++)
                (readers.objectAt(i) as FileView)?.reload();
        }
    }
}
