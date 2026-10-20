// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/services/{Apps,Actions,Schemes}.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root
    signal accepted(string label)
    signal finished(string label)
    signal failed(string message)
    property int pending: 0
    function run(argv, label, directory, waitForExit) {
        if (!argv || !argv.length || pending >= 8) { failed("Hay demasiadas aperturas pendientes."); return false; }
        var job = task.createObject(root, { command: argv, workingDirectory: directory || "", label: label, waitForExit: waitForExit === true });
        pending++;
        job.running = true;
        return true;
    }
    Component {
        id: task
        Process {
            id: job
            required property string label
            property bool waitForExit: false
            property bool didStart: false
            property bool settled: false
            property string detail: ""
            function dispose() {
                if (settled) return;
                settled = true;
                root.pending--;
                destroy();
            }
            stderr: SplitParser { onRead: data => job.detail = data.slice(0, 240) }
            stdout: SplitParser { onRead: function(data) {} }
            onStarted: {
                didStart = true;
                if (!waitForExit) root.accepted(label);
            }
            onExited: (code, status) => {
                if (code !== 0 || status !== 0) root.failed("No se pudo completar «" + label + "» (código " + code + "). " + detail);
                else if (waitForExit) root.finished(label);
                dispose();
            }
            Timer {
                interval: 1200
                running: true
                onTriggered: if (!job.didStart && !job.settled) {
                    root.failed("No se pudo iniciar «" + job.label + "». Comprueba que el ejecutable esté instalado.");
                    job.dispose();
                }
            }
        }
    }
}
