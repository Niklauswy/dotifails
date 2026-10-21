import QtQuick
import Quickshell.Io

// Each widget owns its request stream; emoji and launcher never steal results.
Item {
    id: root
    property string mode: "all"
    property string query
    property bool enabled: true
    property var rows: []
    readonly property bool loading: debounce.running || proc.running
    property int generation: 0
    function refresh(): void { generation++; debounce.restart(); }
    onModeChanged: { rows = []; refresh(); }
    onQueryChanged: { rows = []; refresh(); }
    onEnabledChanged: { if (enabled) refresh(); }
    Component.onCompleted: refresh()
    Timer {
        id: debounce
        interval: 80
        onTriggered: {
            if (root.enabled && !proc.running) proc.start();
        }
    }
    Process {
        id: proc
        property int revision
        function start(): void {
            revision = root.generation;
            command = ["python3", "-I", LauncherData.script, "query", root.mode, root.query];
            running = true;
        }
        stdout: StdioCollector {
            onStreamFinished: {
                if (proc.revision !== root.generation) return;
                try { root.rows = JSON.parse(text); }
                catch (error) { root.rows = [{kind: "error", title: "Unable to load results", subtitle: String(error), section: "Status", icon: "error"}]; }
            }
        }
        onExited: { if (root.enabled && revision !== root.generation) debounce.restart(); }
    }
}
