// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// 6c70d5cb: same card API, backed by Wysun Recorder's existing control protocol.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property bool running: false
    property bool paused: false
    property real elapsed: 0
    property int refCount: 0
    property string error: ''
    function start(extraArgs = []): void {
        // Preparation retains the native portal/consent flow and existing settings.
        Quickshell.execDetached(['wysun', 'recorder', '--quick-record']);
    }
    function stop(): void { if (!control.running) { control.command = ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'record-stop']; control.running = true; } }
    function togglePause(): void { if (!control.running) { control.command = ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'record-pause']; control.running = true; } }
    Process {
        id: status
        command: ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'record-status']
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const state = JSON.parse(text);
                    root.running = state.running; root.paused = state.paused; root.elapsed = state.elapsed;
                } catch (error) { root.error = 'Estado de Recorder no disponible'; }
            }
        }
    }
    Process { id: control; onExited: (code, exitStatus) => { root.error = code || exitStatus ? 'Abre Wysun Recorder para revisar la operación' : ''; status.running = true; } }
    Timer { interval: 1000; running: root.refCount > 0; repeat: true; triggeredOnStart: true; onTriggered: if (!status.running) status.running = true }
}
