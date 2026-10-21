pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.services
import qs.utils

// Standalone session lock (lock.qml, run by wysun-lock). The only path that
// releases the lock is a successful PAM conversation (Pam.authenticated). The
// process never unlocks on IPC, signals or timeouts: if it dies the compositor
// stays locked and wysun-lock relaunches it.
Scope {
    id: root

    // Screen that shows the password form: follows the last input, starts on the focused output.
    property string activeScreen: Hypr.focusedMonitor?.name ?? Quickshell.screens[0]?.name ?? ""
    property bool unlocking
    property string displayName: Quickshell.env("USER") ?? ""
    readonly property string userName: Quickshell.env("USER") ?? ""

    function finish(): void {
        // Release the lock only after the exit animation; the timer is a cap, not a bypass.
        unlocking = true;
        releaseTimer.start();
    }

    WlSessionLock {
        id: lock

        locked: true

        // Last-resort exit codes: 0 only after authentication, 1 if the compositor ended the lock.
        onLockedChanged: {
            if (!locked)
                Qt.exit(root.unlocking ? 0 : 1);
        }
        onSecureChanged: {
            if (secure)
                ready.running = true;
        }

        LockSurface {
            lock: root
            pam: pam
        }
    }

    Pam {
        id: pam

        lock: lock
        onAuthenticated: root.finish()
    }

    Timer {
        id: releaseTimer

        interval: 520
        onTriggered: lock.locked = false
    }

    // Tell wysun-lock the compositor confirmed the lock (the marker only exists on the first launch).
    Process {
        id: ready

        command: ["sh", "-c", "[ -n \"$WYSUN_LOCK_READY\" ] && [ -e \"$WYSUN_LOCK_READY\" ] && printf locked > \"$WYSUN_LOCK_READY\"; exit 0"]
    }

    FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Paths.home + "/.config") + "/orbit/environment.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try {
                Wallpapers.wysunWallpaper = JSON.parse(text()).wallpaper || {};
            } catch (error) {}
        }
    }

    Process {
        running: true
        command: ["sh", "-c", "getent passwd \"$(id -un)\" | cut -d: -f5 | cut -d, -f1"]
        stdout: StdioCollector {
            onStreamFinished: {
                const name = text.trim();
                if (name)
                    root.displayName = name;
            }
        }
    }
}
