// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Original revision: 6c70d5cb. Keeps original NotifData/cards, with Dunst owning the bus and toasts.
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Caelestia.State
import qs.services

Singleton {
    id: root
    property list<NotifData> list: []
    readonly property list<NotifData> notClosed: list.filter(n => !n.closed)
    readonly property list<NotifData> popups: []
    readonly property bool active: ShellState.anySidebarOpen()
    property string error: ''
    property bool loaded: true
    function hasFullscreen(): bool { return false; }
    function shouldShowPopup(): bool { return false; }
    function refresh(): void { if (active && !history.running) history.running = true; }
    function dismiss(identifier: string): void {
        if (/^[0-9]+$/.test(identifier))
            Quickshell.execDetached(['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'dismiss', identifier]);
    }
    function toggleDnd(): void { if (!dnd.running) dnd.running = true; }
    Process {
        id: dnd
        command: ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'dnd']
        stdout: StdioCollector { onStreamFinished: { try { PersistentState.doNotDisturb = JSON.parse(text).paused; } catch (error) {} } }
        onExited: (code, status) => { if (code || status) root.error = 'No se pudo cambiar No molestar'; }
    }
    onActiveChanged: refresh()
    Process {
        id: history
        command: ['/usr/bin/python3', Quickshell.shellPath('wysun/backend.py'), 'history']
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const rows = JSON.parse(text);
                    if (!Array.isArray(rows)) throw Error('Historial inválido');
                    const old = root.list;
                    root.list = rows.map(row => notifComp.createObject(root, Object.assign({historyOnly: true}, row)));
                    for (const item of old) item.destroy();
                    root.error = '';
                } catch (error) { root.error = 'Historial Dunst no disponible'; }
            }
        }
        onExited: (code, status) => { if (code || status) root.error = 'Historial Dunst no disponible'; }
    }
    Timer { interval: 5000; running: root.active; repeat: true; onTriggered: root.refresh() }
    IpcHandler {
        target: 'notifs'
        function clear(): void { for (const notif of root.list.slice()) notif.close(); }
    }
    Component { id: notifComp; NotifData {} }
}
