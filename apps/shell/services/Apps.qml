// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/services/Apps.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import Quickshell
import "../modules/launcher" as Launcher
import "../modules/launcher/Logic.js" as Logic

Scope {
    id: root
    property var entries: DesktopEntries.applications.values
    signal accepted(string label)
    signal failed(string message)
    function query(text) { return Logic.appSearch(entries, text); }
    function launch(entry) {
        if (!entry || entries.indexOf(entry) < 0 || entry.noDisplay || !entry.command.length) {
            failed("La aplicación ya no está disponible. Vuelve a buscarla."); return false;
        }
        // DesktopEntry owns terminal command/field-code handling in Quickshell 0.3.
        // Its execute() has no completion result; do not claim terminal startup proof.
        if (entry.runInTerminal) {
            try { entry.execute(); accepted(entry.name); return true; }
            catch (error) { failed("No se pudo solicitar la terminal: " + error); return false; }
        }
        return dispatch.run(Array.from(entry.command), entry.name, entry.workingDirectory, false);
    }
    Launcher.Dispatcher {
        id: dispatch
        onAccepted: label => root.accepted(label)
        onFailed: message => root.failed(message)
    }
}
