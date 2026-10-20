// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/services/Actions.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import Quickshell
import "../modules/launcher" as Launcher
import "../modules/launcher/Logic.js" as Logic

Scope {
    id: root
    signal accepted(string label)
    signal failed(string message)

    function query(text) {
        return Logic.search(Logic.modes.concat(Logic.actions), text, ["name", "id", "description"]);
    }

    function launch(id) {
        var argv = Logic.actionArgv(id);
        if (!argv.length) {
            failed("Acción no permitida.");
            return false;
        }
        return dispatch.run(argv, id, "", false);
    }

    Launcher.Dispatcher {
        id: dispatch
        onAccepted: label => root.accepted(label)
        onFailed: message => root.failed(message)
    }
}
