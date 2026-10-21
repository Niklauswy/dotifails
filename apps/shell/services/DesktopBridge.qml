// Wysun: JSON calls to the desktop backends (displays, shortcuts, rules, startup, backups, SSH, processes).
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property string script: Quickshell.shellPath('wysun/desktop_bridge.py')

    // Run one bridge action. `done(data)` on success, `failed(message)` otherwise.
    function call(action: string, args: var, done: var, failed: var): void {
        callComp.createObject(root, { command: ['/usr/bin/python3', root.script, action, JSON.stringify(args ?? {})], done: done, failed: failed, running: true });
    }

    // Long-lived bridge process (e.g. process snapshots); the caller owns it.
    function streamCommand(action: string, args: var): var {
        return ['/usr/bin/python3', root.script, action, JSON.stringify(args ?? {})];
    }

    Component {
        id: callComp

        Process {
            id: proc

            property var done
            property var failed

            stdout: StdioCollector {
                onStreamFinished: {
                    let reply = null;
                    try { reply = JSON.parse(text); } catch (error) { reply = null; }
                    if (reply && reply.ok) {
                        if (proc.done) proc.done(reply.data);
                    } else if (proc.failed) {
                        proc.failed(reply ? reply.error : 'El servicio de ajustes no respondió.');
                    }
                    proc.destroy();
                }
            }
        }
    }
}
