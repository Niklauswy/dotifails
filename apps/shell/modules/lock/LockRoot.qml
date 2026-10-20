// Proceso de bloqueo QML opt-in de Wysun. Usa WlSessionLock de Quickshell 0.3
// (ext-session-lock-v1): si este proceso muere con la sesión bloqueada, el
// compositor no la desbloquea. La autenticación usa PamContext con un
// configDirectory empaquetado que incluye /etc/pam.d/login; no se modifica
// /etc/pam.d, no se copia Pam.qml y no hay IPC de desbloqueo.
// Presentación derivada de caelestia-dots/shell modules/lock/{Center,Content,
// Media}.qml y center/, commit 507d66285e9d9fde9330adc64159cfdebb28c19a
// (GPL-3.0), modificada para Wysun. Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import "../.." as Wysun
import "../../services" as Services

Scope {
    id: root

    readonly property string shellRoot: Quickshell.env("WYSUN_SHELL_ROOT") || Quickshell.shellPath(".")
    readonly property string readyMarker: Quickshell.env("WYSUN_LOCK_READY") || ""
    readonly property bool mediaEnabled: Quickshell.env("WYSUN_LOCK_MEDIA") === "1"
    property bool ready: false

    function markReady() {
        if (root.ready) return;
        var marker = root.readyMarker;
        if (marker.length === 0 || marker[0] !== "/" || /[\x00-\x1f\x7f]/.test(marker)) {
            console.warn("Wysun Lock: no hay marcador de disponibilidad; se continúa bloqueado.");
        } else {
            readyProcess.command = ["/bin/sh", "-c", "umask 077; printf '%s' locked > \"$1\"", "sh", marker];
            readyProcess.running = true;
        }
        root.ready = true;
    }

    function unlockNow() {
        if (!lock.secure || !lock.locked) return;
        auth.abort();
        lock.locked = false;
        unlockWatch.start();
    }

    LockTheme {
        id: theme
        shellRoot: root.shellRoot
    }
    Services.Colours { id: colours }
    Wysun.Motion {
        id: motion
        reducedMotion: theme.appearance.reducedMotion
    }
    FontLoader {
        source: root.shellRoot + "/assets/fonts/Rubik-Variable.ttf"
        onStatusChanged: if (status === FontLoader.Ready) Wysun.Appearance.refreshFonts()
    }

    WlSessionLock {
        id: lock

        locked: true
        surface: Component {
            OutputLock {
                sessionLock: lock
                auth: auth
                mediaEnabled: root.mediaEnabled
                motion: motion
            }
        }
    }

    LockAuth {
        id: auth
        secure: lock.secure
        configDirectory: root.shellRoot + "/config/pam.d"
        onAuthenticated: root.unlockNow()
    }

    Connections {
        target: lock
        function onSecureChanged() {
            if (lock.secure) root.markReady();
        }
        function onLockStateChanged() {
            if (!lock.locked) quitTimer.start();
        }
    }

    // If the compositor never confirms the lock, exit non-zero so wysun-lock
    // can fall back to swaylock instead of pretending the session is secured.
    Timer {
        interval: 15000
        running: !lock.secure
        repeat: false
        onTriggered: {
            if (!lock.secure) Qt.exit(3);
        }
    }
    Timer {
        id: quitTimer
        interval: 500
        repeat: false
        onTriggered: Qt.exit(0)
    }
    Timer {
        id: unlockWatch
        interval: 3000
        repeat: false
        onTriggered: {
            if (lock.locked) {
                auth.state = "error";
                auth.detail = "no se pudo desbloquear la sesión";
            }
        }
    }

    Process {
        id: readyProcess
        onExited: function(code) {
            if (code !== 0) console.warn("Wysun Lock: no se pudo publicar la disponibilidad.");
        }
    }
}
