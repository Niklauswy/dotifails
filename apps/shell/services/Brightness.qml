// Adaptado de caelestia-dots/shell/services/Brightness.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// Wysun adaptation: one explicit laptop backlight, observed through
// /sys/class/backlight/<device>/{brightness,actual_brightness} with FileView (no polling). Writes
// stay in brightnessctl so the desktop's existing udev permissions are used.
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root

    readonly property string sysfsRoot: Quickshell.env("WYSUN_BACKLIGHT_ROOT") || "/sys/class/backlight"
    // Disabled instances (gallery, tests) never run brightnessctl.
    property bool enabled: true
    property string device: ""
    property bool available: false
    property bool busy: false
    property string error: ""
    property int current: 0
    property int maximum: 0
    readonly property real value: maximum > 0 ? current / maximum : 0
    property bool settled: false
    property real lastValue: 0
    signal changed(real value)

    Component.onCompleted: if (enabled) discover.running = true

    function acceptDevice(text) {
        var line = String(text || "").split("\n").find(part => part.trim().length > 0);
        if (!line) {
            error = "No se encontró una pantalla con brillo ajustable";
            return;
        }
        var fields = line.trim().split(",");
        var name = fields[0] || "";
        var currentValue = parseInt(fields[2], 10);
        var maximumValue = parseInt(fields[4], 10);
        if (fields.length !== 5 || fields[1] !== "backlight" || !/^[A-Za-z0-9_:.+-]+$/.test(name)
                || !isFinite(currentValue) || !isFinite(maximumValue) || maximumValue <= 0) {
            error = "El dispositivo de brillo no es válido";
            return;
        }
        device = name;
        current = currentValue;
        maximum = maximumValue;
        available = true;
        error = "";
        settled = false;
        settle.restart();
    }

    function sync() {
        // actual_brightness is the attribute the kernel notifies on hardware or
        // firmware changes; brightness covers writes made through sysfs.
        var actualValue = parseInt(actualView.text(), 10);
        var currentValue = isFinite(actualValue) ? actualValue : parseInt(currentView.text(), 10);
        var maximumValue = parseInt(maxView.text(), 10);
        if (!isFinite(currentValue) || !isFinite(maximumValue) || maximumValue <= 0)
            return;
        current = currentValue;
        maximum = maximumValue;
        if (!settled) return;
        if (Math.abs(value - lastValue) < 0.0001) return;
        lastValue = value;
        changed(value);
    }

    function setBrightness(value) {
        if (!available || busy) return false;
        var percent = Math.max(5, Math.min(100, Math.round(Number(value) * 100)));
        write.command = ["brightnessctl", "-c", "backlight", "-d", device, "set", percent + "%"];
        busy = true;
        error = "";
        write.running = true;
        return true;
    }

    function retry() {
        error = "";
        available = false;
        device = "";
        discover.running = true;
    }

    Timer {
        id: settle
        interval: 250
        onTriggered: {
            root.settled = true;
            root.lastValue = root.value;
        }
    }

    Process {
        id: discover
        command: ["brightnessctl", "-m", "-c", "backlight", "info"]
        stdout: StdioCollector { id: discovery; onStreamFinished: root.acceptDevice(text) }
        stderr: StdioCollector { }
        onExited: (code, status) => {
            if ((code !== 0 || status !== 0) && !root.available)
                root.error = "No hay brillo de pantalla disponible";
        }
    }

    Process {
        id: write
        stderr: StdioCollector { onStreamFinished: if (text.trim().length > 0) root.error = "No se pudo cambiar el brillo" }
        onExited: (code, status) => {
            root.busy = false;
            if (code !== 0 || status !== 0) root.error = "No se pudo cambiar el brillo";
        }
    }

    FileView {
        id: currentView
        path: root.device ? root.sysfsRoot + "/" + root.device + "/brightness" : ""
        watchChanges: true
        blockLoading: true
        printErrors: false
        onLoaded: root.sync()
        onFileChanged: reload()
        onLoadFailed: error => { if (root.device) root.error = "No se pudo leer el brillo del sistema"; }
    }

    FileView {
        id: actualView
        path: root.device ? root.sysfsRoot + "/" + root.device + "/actual_brightness" : ""
        watchChanges: true
        blockLoading: true
        printErrors: false
        onLoaded: root.sync()
        onFileChanged: reload()
    }

    FileView {
        id: maxView
        path: root.device ? root.sysfsRoot + "/" + root.device + "/max_brightness" : ""
        watchChanges: true
        blockLoading: true
        printErrors: false
        onLoaded: root.sync()
        onFileChanged: reload()
        onLoadFailed: error => { if (root.device) root.error = "No se pudo leer el brillo máximo"; }
    }
}
