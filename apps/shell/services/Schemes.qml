// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/services/Schemes.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import Quickshell
import Quickshell.Io
import "../modules/launcher" as Launcher
import "../modules/launcher/Logic.js" as Logic

Scope {
    id: root
    property var wallpapers: []
    property bool loading: listing.running
    readonly property bool busy: dispatch.pending > 0
    signal finished(string label)
    signal failed(string message)

    function query(text) {
        return Logic.search(Logic.schemes, text, ["name", "id", "description"]);
    }
    function wallpaperQuery(text) {
        return Logic.search(wallpapers, text, ["name"]);
    }
    function select(id) {
        var argv = Logic.schemeArgv(id);
        if (!argv.length) {
            failed("Esquema desconocido.");
            return false;
        }
        return dispatch.run(argv, "esquema de color", "", true);
    }
    function selectVariant(id) {
        var argv = Logic.variantArgv(id);
        if (!argv.length) {
            failed("Variante desconocida.");
            return false;
        }
        return dispatch.run(argv, "variante Material You", "", true);
    }
    function reload() {
        if (!listing.running) listing.running = true;
    }
    function selectWallpaper(path) {
        if (!wallpapers.some(row => row.path === path)) {
            failed("El fondo ya no está disponible. Vuelve a consultar la lista.");
            return false;
        }
        return dispatch.run(["wysun", "wallpaper", "set", path], "Ajustes de fondo", "", true);
    }

    Launcher.Dispatcher {
        id: dispatch
        onFinished: label => {
            root.reload();
            root.finished(label);
        }
        onFailed: message => root.failed(message)
    }

    Process {
        id: listing
        property bool didStart: false
        property string detail: ""
        command: ["python3", Quickshell.shellPath("modules/launcher/backend.py"), "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(text);
                    if (!Array.isArray(data) || data.length > 512) throw Error("lista inválida");
                    root.wallpapers = data;
                } catch (error) {
                    root.wallpapers = [];
                    root.failed("No se pudo leer la lista de fondos. Revisa Ajustes de Wysun.");
                }
            }
        }
        stderr: SplitParser {
            onRead: data => {
                if (String(data).trim()) listing.detail = String(data).slice(0, 240);
            }
        }
        onStarted: didStart = true
        onRunningChanged: {
            if (running) {
                didStart = false;
                detail = "";
                startCheck.restart();
            }
        }
        onExited: (code, status) => {
            if (code !== 0 || status !== 0) {
                root.wallpapers = [];
                root.failed("No se pudieron consultar los fondos."
                    + (listing.detail ? " " + listing.detail : " Revisa Ajustes de Wysun."));
            }
        }
    }
    Timer {
        id: startCheck
        interval: 1200
        onTriggered: {
            if (!listing.didStart)
                root.failed("No se encuentra Python para consultar los fondos de Wysun.");
        }
    }
}
