// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: services/{Audio,Brightness,Nmcli,Notifs}.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root
    property bool active: false
    property string domains: "audio,brightness,network,bluetooth,battery,notifications"
    property var states: ({})
    property bool fixture: false
    property string fixturePath: ""
    property string error: ""
    property string warning: ""
    property string operation: ""
    property string actionName: ""
    readonly property bool busy: process.running
    signal feedback(string channel, real percent, bool muted)

    function run(operation, name, value) {
        if (busy || !active) return false;
        root.operation = operation;
        root.actionName = name;
        error = "";
        warning = "";
        var args = ["python3", Quickshell.shellPath("services/desktop_controls.py"), operation, name];
        if (operation === "action") args.push(String(value === undefined ? "" : value));
        if (fixture) {
            if (!fixturePath) { error = "La vista previa no controla dispositivos"; return false; }
            args.push("--fixture", fixturePath);
        }
        process.command = args;
        process.running = true;
        return true;
    }
    function refresh() { return run("snapshot", domains, ""); }
    function act(name, value) { return run("action", name, value); }
    function accept(text) {
        try {
            var result = JSON.parse(text);
            if (!result.ok) { error = result.error || "No se pudo completar la operación"; return; }
            if (result.states) states = result.states;
            if (result.domain && result.state) {
                var updated = Object.assign({}, states);
                updated[result.domain] = result.state;
                states = updated;
                warning = result.warning || "";
                if (result.state.available && ["audio", "brightness"].indexOf(result.domain) >= 0)
                    feedback(result.domain, result.state.percent, result.state.muted || false);
            }
        } catch (e) { error = "Respuesta del proveedor inválida"; }
    }
    onActiveChanged: if (active) refresh()
    Component.onCompleted: if (active) refresh()
    // Explicit refresh and action readback only. No timer or monitor while closed.
    Process {
        id: process
        stdout: StdioCollector { onStreamFinished: root.accept(text) }
        stderr: StdioCollector {}
        onExited: (code, status) => {
            if ((code !== 0 || status !== 0) && !root.error)
                root.error = "El proveedor no respondió. Actualiza el panel.";
        }
    }
}
