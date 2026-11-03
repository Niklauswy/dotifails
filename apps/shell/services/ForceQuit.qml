pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Hyprland
import "../modules/forcequit/ForceQuitLogic.js" as Logic

// Super+Shift+Esc (`wysun-shell forcequit`): the shell asks, over the active window, whether to force it closed;
// Enter kills its client, Escape, a click elsewhere or 12 s cancel. Pieces of the session are never offered. modules/forcequit draws it.
Singleton {
    id: root

    property var target: null            // {address, cls, title, pid, at, size, monitor}
    readonly property bool showing: target !== null

    function request(): bool {
        const t = Hyprland.activeToplevel;
        const ipc = t?.lastIpcObject;
        const win = ipc ? {address: ipc.address, cls: ipc.class, title: ipc.title, pid: ipc.pid, at: ipc.at, size: ipc.size,
                           monitor: t.monitor?.name ?? ""} : null;
        if (!Logic.canForceQuit(win))
            return false;
        target = win;
        expire.restart();
        return true;
    }

    function confirm(): void {
        if (target)
            Quickshell.execDetached(["kill", "-KILL", String(target.pid)]);
        target = null;
    }

    function cancel(): void {
        target = null;
    }

    // It holds the keyboard: never for long.
    Timer {
        id: expire

        interval: 12000
        onTriggered: root.target = null
    }
}
