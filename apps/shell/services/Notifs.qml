// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Original revision: 6c70d5cb. The shell owns org.freedesktop.Notifications (no separate notification daemon).
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Notifications
import Wysun.Config
import Wysun.State
import qs.services

Singleton {
    id: root

    property list<NotifData> list: []
    readonly property list<NotifData> notClosed: list.filter(n => !n.closed)
    readonly property list<NotifData> popups: list.filter(n => n.popup)
    readonly property bool dnd: PersistentState.doNotDisturb
    property string error: ""
    property bool loaded: true

    // Only fullscreen apps on the focused monitor suppress toasts (the same rule NotifData uses to expire them).
    function hasFullscreen(): bool {
        const monitor = Hypr.focusedMonitor;
        const specialName = monitor?.lastIpcObject.specialWorkspace?.name;
        if (specialName) {
            const specialWs = Hypr.workspaces.values.find(ws => ws.name === specialName);
            return specialWs?.toplevels.values.some(t => t.lastIpcObject.fullscreen > 1) ?? false;
        }
        return monitor?.activeWorkspace?.toplevels.values.some(t => t.lastIpcObject.fullscreen > 1) ?? false;
    }

    function shouldShowPopup(): bool {
        return !dnd;
    }

    function setDnd(value: bool): void {
        PersistentState.doNotDisturb = value;
        if (value)
            list.forEach(n => n.popup = false);
    }

    function toggleDnd(): void {
        setDnd(!dnd);
    }

    // History entries are real notifications now; dismissing one just closes it.
    function dismiss(identifier: string): void {
        const target = list.find(n => String(n.notificationId) === String(identifier));
        target?.close();
    }

    function clear(): void {
        for (const notif of list.slice())
            notif.close();
    }

    NotificationServer {
        keepOnReload: false
        actionsSupported: true
        bodyHyperlinksSupported: true
        bodyImagesSupported: true
        bodyMarkupSupported: true
        imageSupported: true
        persistenceSupported: true

        onNotification: notification => {
            notification.tracked = true;
            const entry = notifComp.createObject(root, {
                popup: root.shouldShowPopup(),
                notification: notification
            });
            root.list = [entry, ...root.list];
        }
    }

    IpcHandler {
        target: "notifs"

        function clear(): void {
            root.clear();
        }

        function toggleDnd(): void {
            root.toggleDnd();
        }

        function setDnd(value: bool): void {
            root.setDnd(value);
        }

        // JSON for scripts (recorder, status bars): {"dnd": bool, "count": int}
        function status(): string {
            return JSON.stringify({
                dnd: root.dnd,
                count: root.notClosed.length
            });
        }
    }

    Component {
        id: notifComp

        NotifData {}
    }
}
