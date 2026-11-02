pragma Singleton

import QtQuick
import Qt.labs.folderlistmodel
import Quickshell
import Quickshell.Io
import "LanShareLogic.js" as Logic

// Running Wysun LANShare servers, read from the status files each one keeps in
// $XDG_RUNTIME_DIR/wysun-lanshare/<pid>.json (apps/python/wysun_lanshare/status.py). The bar
// only shows and stops them; sharing starts from a terminal or from Files. A file without a
// heartbeat for 30 s belongs to a dead server and is ignored.
Singleton {
    id: root

    readonly property string dir: `${Quickshell.env("XDG_RUNTIME_DIR")}/wysun-lanshare`
    property var files: ({})
    property real now: Date.now() / 1000
    readonly property var servers: Logic.live(Object.values(files), now)
    readonly property bool active: servers.length > 0
    readonly property bool busy: servers.some(s => (s.transfers ?? []).length > 0)

    function stop(pid: int): void {
        Quickshell.execDetached(["wysun", "lanshare", "--detener", String(pid)]);
    }

    function copy(text: string): void {
        Quickshell.clipboardText = text;
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

    // Countdown and heartbeat: re-read while something is shared (atomic writes replace the file).
    Timer {
        interval: 2000
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
