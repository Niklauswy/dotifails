pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "CloudVmsLogic.js" as Logic

// Running Google Cloud VMs, read from $XDG_RUNTIME_DIR/wysun-cloud/state.json, which both
// `wysun cloud` and `wysun cloud --estado` write (apps/python/wysun_cloud/state.py). The bar
// only shows the count; clicking opens the TUI in a terminal. A state older than ten minutes
// is ignored (CloudVmsLogic.js), so a gcloud failure never leaves stale VMs forever.
Singleton {
    id: root

    readonly property string path: `${Quickshell.env("XDG_RUNTIME_DIR")}/wysun-cloud/state.json`
    property var state: null
    property real now: Date.now() / 1000
    readonly property var vms: Logic.running(state, now)
    readonly property bool active: vms.length > 0

    function open(): void {
        Quickshell.execDetached(["wysun", "cloud", "--terminal"]);
    }

    function put(text: string): void {
        try {
            state = JSON.parse(text);
        } catch (error) {
            // An atomic write never leaves half a file, but a foreign one must not break the bar.
            state = null;
        }
    }

    FileView {
        id: stateFile

        path: root.path
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.put(text())
        onLoadFailed: root.state = null
    }

    Process {
        id: refresher

        command: ["wysun", "cloud", "--estado"]
        onExited: stateFile.reload()
    }

    // Poll every two minutes, also once at start; the clock update hides a stale state even
    // when gcloud fails and the file keeps its old `updated`.
    Timer {
        interval: 120000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            root.now = Date.now() / 1000;
            if (!refresher.running)
                refresher.running = true;
        }
    }
}
