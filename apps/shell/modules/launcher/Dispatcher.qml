// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/launcher/services/{Apps,Actions,Schemes}.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import Quickshell
import Quickshell.Io

// Bounded command dispatcher. Commands come from the launcher allowlist or a
// DesktopEntry, never from the query text. The object stays alive while a
// launched application runs so closing the launcher does not kill it.
Scope {
    id: root
    signal accepted(string label)
    signal finished(string label)
    signal failed(string message)
    property int pending: 0

    function run(argv, label, directory, waitForExit) {
        if (!argv || !argv.length || pending >= 8) {
            failed("Hay demasiadas aperturas pendientes.");
            return false;
        }
        var job = task.createObject(root, {
            command: argv,
            workingDirectory: directory || "",
            label: label,
            waitForExit: waitForExit === true
        });
        job.guard = guard.createObject(root, { job: job });
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
            property bool counted: true
            property string detail: ""
            property var guard: null

            function release() {
                if (!counted) return;
                counted = false;
                root.pending = Math.max(0, root.pending - 1);
            }
            function stopGuard() {
                if (guard) {
                    guard.destroy();
                    guard = null;
                }
            }
            function dispose() {
                if (settled) return;
                settled = true;
                release();
                stopGuard();
                destroy();
            }

            stderr: SplitParser {
                onRead: data => {
                    if (String(data).trim()) job.detail = String(data).slice(0, 240);
                }
            }
            stdout: SplitParser { onRead: function(data) {} }

            onStarted: {
                didStart = true;
                stopGuard();
                if (!waitForExit) {
                    // The application is running; free the dispatch slot but keep
                    // the Process object so it can outlive this launcher card.
                    release();
                    root.accepted(label);
                }
            }
            onExited: (code, status) => {
                if (code !== 0 || status !== 0) {
                    if (waitForExit || !job.didStart)
                        root.failed("No se pudo completar «" + label + "» (código " + code + ")." + (job.detail ? " " + job.detail : ""));
                } else if (waitForExit) {
                    root.finished(label);
                }
                dispose();
            }
        }
    }

    Component {
        id: guard
        Timer {
            id: timer
            property var job
            interval: 1200
            running: true
            onTriggered: {
                if (job && !job.didStart && !job.settled) {
                    root.failed("No se pudo iniciar «" + job.label + "»."
                        + (job.detail ? " " + job.detail : " Comprueba que el ejecutable esté instalado."));
                    job.dispose();
                }
            }
        }
    }
}
