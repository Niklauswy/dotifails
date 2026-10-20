// Adaptado de caelestia-dots/shell/services/{Audio,Brightness,Nmcli,Notifs}.qml
// (GPL-3.0), modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// One bounded, one-shot provider bridge. It is active only while its surface is
// open: no daemon, retry loop or timer keeps running behind a closed panel.
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root

    property bool active: false
    property string domains: "network,bluetooth,battery,notifications,session"
    property var states: ({})
    property bool fixture: false
    property string fixturePath: ""
    property string error: ""
    property string warning: ""
    property string operation: ""
    property string actionName: ""
    readonly property bool busy: request.running
    property bool refreshPending: false
    signal updated()
    signal actionDone(string name)

    function refreshLater() {
        if (refreshPending) return;
        refreshPending = true;
        Qt.callLater(function() { refreshPending = false; refresh(); });
    }

    function run(operation, name, value) {
        if (!active) return false;
        if (request.running) {
            error = "Hay otra operación en curso";
            return false;
        }
        root.operation = operation;
        root.actionName = name;
        error = "";
        warning = "";
        var args = ["/usr/bin/python3", Quickshell.shellPath("services/desktop_controls.py"), operation, name];
        if (operation === "action") args.push(String(value === undefined ? "" : value));
        if (fixture) {
            if (!fixturePath) {
                error = "La vista previa no controla dispositivos";
                return false;
            }
            args.push("--fixture", fixturePath);
        }
        request.command = args;
        request.running = true;
        timeout.restart();
        return true;
    }

    function refresh() { return run("snapshot", domains, ""); }
    function act(name, value) { return run("action", name, value); }
    function domain(name) {
        var value = states && states[name];
        return value && typeof value === "object" ? value : ({ available: false, error: "Sin datos" });
    }

    function accept(text) {
        var result;
        try { result = JSON.parse(text); }
        catch (error) { root.error = "Respuesta del proveedor inválida"; return; }
        if (!result || !result.ok) {
            root.error = result && result.error ? result.error : "No se pudo completar la operación";
            return;
        }
        if (result.states) {
            var merged = Object.assign({}, root.states);
            for (var key in result.states) merged[key] = result.states[key];
            root.states = merged;
        }
        if (result.domain && result.state) {
            var updated = Object.assign({}, root.states);
            updated[result.domain] = result.state;
            root.states = updated;
        }
        warning = result.warning || "";
        updated();
        if (operation === "action") actionDone(actionName);
    }

    onActiveChanged: {
        if (active) refreshLater();
        else if (request.running) request.running = false;
    }
    Component.onCompleted: if (active) refreshLater()

    Timer {
        id: timeout
        interval: 5000
        repeat: false
        onTriggered: {
            if (!request.running) return;
            request.running = false;
            root.error = "El proveedor no respondió a tiempo";
        }
    }

    Process {
        id: request
        stdout: StdioCollector { onStreamFinished: root.accept(text) }
        stderr: StdioCollector { }
        onExited: (code, status) => {
            timeout.stop();
            if ((code !== 0 || status !== 0) && !root.error)
                root.error = root.operation === "snapshot"
                    ? "El proveedor no respondió. Actualiza el panel."
                    : "No se pudo completar la acción";
        }
    }
}
