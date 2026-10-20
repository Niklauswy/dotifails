// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Resources.qml; modules/dashboard/performance/, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import Quickshell
import Quickshell.Io
import "../../../" as Wysun
import "../Logic.js" as Logic

Scope {
    id: root
    required property bool enabled
    readonly property var cpu: stats.sample?.percent ?? null
    readonly property var memory: stats.memory
    property var storage: null
    // Optional providers may be supplied later; absence never becomes zero.
    property var cpuTemperature: null
    property var gpu: null
    property var gpuTemperature: null
    Wysun.ResourceStats { id: stats; enabled: root.enabled }
    onEnabledChanged: {
        storage = null; cpuTemperature = null; gpu = null; gpuTemperature = null;
        if (enabled) sampleStorage();
    }
    function sampleStorage() {
        if (!disk.running) disk.running = true;
        if (!sensors.running) sensors.running = true;
    }
    Component.onCompleted: if (enabled) sampleStorage()
    Timer { interval: 5000; running: root.enabled; repeat: true; onTriggered: root.sampleStorage() }
    Process {
        id: disk
        command: ["df", "-Pk", "/"]
        environment: ({ "LC_ALL": "C" })
        stdout: StdioCollector { onStreamFinished: if (root.enabled) root.storage = Logic.storagePercent(text) }
        onExited: (code, status) => { if (code !== 0 || status !== 0) root.storage = null; }
    }
    // Read-only sysfs sample. Sensors that do not exist print nothing, and the
    // parser then leaves the value null ("No disponible" in the UI).
    Process {
        id: sensors
        command: ["sh", "-c", "for d in /sys/class/hwmon/hwmon*; do n=$(cat \"$d/name\" 2>/dev/null) || continue; t=$(cat \"$d/temp1_input\" 2>/dev/null) && echo \"T $n $t\"; done; for f in /sys/class/drm/card*/device/gpu_busy_percent; do [ -r \"$f\" ] && { echo \"G $(cat \"$f\")\"; break; }; done; exit 0"]
        environment: ({ "LC_ALL": "C" })
        stdout: StdioCollector {
            onStreamFinished: {
                if (!root.enabled) return;
                var r = Logic.parseSensors(text);
                root.cpuTemperature = r.cpuTemperature;
                root.gpuTemperature = r.gpuTemperature;
                root.gpu = r.gpu;
            }
        }
    }
}
