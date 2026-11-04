pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils
import "WysunUpdateLogic.js" as Logic

// Whether the Wysun source has new commits (the bar shows an icon only then). The state is the
// JSON of $XDG_STATE_HOME/wysun/update.json written by `wysun update --check`, which runs three
// minutes after the shell starts and then every hour. `wysun update` may ask for sudo, so it is
// applied in a terminal, never from the bar.
Singleton {
    id: root

    readonly property string path: `${Paths.state}/update.json`
    readonly property bool available: state.available
    readonly property int behind: state.behind
    readonly property string checked: state.checked
    readonly property string branch: state.branch
    readonly property string error: state.error
    property bool checking: false
    property var state: Logic.empty()

    function check(): void {
        if (runner.running)
            return;
        checking = true;
        runner.running = true;
        guard.restart();
    }

    function apply(): void {
        Quickshell.execDetached(["wysun-terminal", "-e", "wysun", "update"]);
    }

    function put(text: string): void {
        state = Logic.parse(text);
    }

    FileView {
        id: stateFile

        path: root.path
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.put(text())
        onLoadFailed: root.state = Logic.empty()
    }

    Process {
        id: runner

        command: ["wysun", "update", "--check"]
        onExited: {
            guard.stop();
            root.checking = false;
            stateFile.reload();
        }
    }

    // A fetch stuck on the network must not keep «Comprobar ahora» disabled forever.
    Timer {
        id: guard

        interval: 2 * 60 * 1000
        onTriggered: {
            runner.running = false;
            root.checking = false;
        }
    }

    Timer {
        interval: 3 * 60 * 1000
        running: true
        onTriggered: root.check()
    }

    Timer {
        interval: 60 * 60 * 1000
        running: true
        repeat: true
        onTriggered: root.check()
    }
}
