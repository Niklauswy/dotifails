import QtQuick
import Quickshell.Io

Item {
    id: root
    property int clipId: -1
    readonly property string request: clipId >= 0 ? "clip:" + clipId : path
    property string path
    property var data: ({})
    property string runningPath
    onRequestChanged: { data = {}; debounce.restart(); }
    Timer {
        id: debounce
        interval: 160
        onTriggered: {
            if (!root.request || proc.running) return;
            root.runningPath = root.request;
            proc.command = ["python3", "-I", LauncherData.script, root.clipId >= 0 ? "preview-clip" : "preview", root.clipId >= 0 ? String(root.clipId) : root.path];
            proc.running = true;
        }
    }
    Process {
        id: proc
        environment: ({QT_QPA_PLATFORM: "offscreen"})
        stdout: StdioCollector {
            onStreamFinished: {
                if (root.request !== root.runningPath) return;
                try { root.data = JSON.parse(text); } catch (error) { root.data = {}; }
            }
        }
        onExited: { if (root.request !== root.runningPath) debounce.restart(); }
    }
}
