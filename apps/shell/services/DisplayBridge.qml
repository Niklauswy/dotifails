pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root

    readonly property string script: Quickshell.shellPath('wysun/display_bridge.py')

    // Run one bridge action. `done(data)` on success, `failed(message)` otherwise.
    function call(action: string, args: var, done: var, failed: var): void {
        callComp.createObject(root, { command: ['/usr/bin/python3', root.script, action, JSON.stringify(args ?? {})], done: done, failed: failed, running: true });
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
                        proc.failed(reply ? reply.error : 'Wysun display services did not respond.');
                    }
                    proc.destroy();
                }
            }
        }
    }
}
