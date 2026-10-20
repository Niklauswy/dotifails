import QtQuick
import Quickshell
import Quickshell.Io
import "Logic.js" as Logic

Scope {
    id: root
    required property bool enabled
    property var sample: null
    property var memory: null
    readonly property string label: Logic.resourceLabel(sample?.percent, memory)
    onEnabledChanged: { sample = null; memory = null; }
    // CPU counters have no event API: one sampler for all visible bars which
    // request this legacy module, and no subprocess per monitor.
    Timer {
        interval: 3000
        repeat: true
        running: root.enabled
        triggeredOnStart: true
        onTriggered: { cpu.reload(); mem.reload(); }
    }
    FileView {
        id: cpu
        path: "/proc/stat"
        // With preload false, reload only invalidates cached data; no read is
        // started until text() is accessed. onLoaded cannot start that first read.
        preload: root.enabled
        blockLoading: false
        printErrors: false
        onLoaded: if (root.enabled) root.sample = Logic.cpuSample(text(), root.sample)
    }
    FileView {
        id: mem
        path: "/proc/meminfo"
        preload: root.enabled
        blockLoading: false
        printErrors: false
        onLoaded: if (root.enabled) root.memory = Logic.memoryPercent(text())
    }
}
