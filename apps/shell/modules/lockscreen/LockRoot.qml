// Wysun Lock · the session lock process (ext-session-lock-v1 through Quickshell's WlSessionLock).
// If this process dies while locked, the compositor keeps the session locked. There is no IPC to
// unlock: only a successful PAM conversation unlocks, after the refinement and the elevator doors.
// The scene lives on one monitor (WYSUN_LOCK_OUTPUT, the one in use when locking; otherwise the
// first); the others stay dark and pass what is typed on them to it.
// It deliberately loads no shell services (notifications, audio, network…), only its own pieces.
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Wysun.Config

Scope {
    id: root

    readonly property string readyMarker: Quickshell.env("WYSUN_LOCK_READY") || ""
    readonly property string shaderDir: Quickshell.env("WYSUN_LOCK_SHADERS") || ""
    readonly property bool reducedMotion: Quickshell.env("ORBIT_REDUCED_MOTION") === "1"
    readonly property string username: Quickshell.env("USER") || ""
    // A snapshot of the primary monitor taken by wysun-lock before locking (private runtime dir); the
    // elevator opens on it when unlocking. Removed when the lock exits.
    readonly property string desktop: Quickshell.env("WYSUN_LOCK_DESKTOP") || ""
    readonly property string output: {
        const wanted = Quickshell.env("WYSUN_LOCK_OUTPUT") || "";
        const names = Quickshell.screens.map(screen => screen.name);
        return names.indexOf(wanted) >= 0 ? wanted : (names[0] || "");
    }
    property LockScene scene: null
    property bool ready: false
    property bool leaving: false

    function markReady(): void {
        if (root.ready)
            return;
        root.ready = true;
        const marker = root.readyMarker;
        if (marker.length === 0 || marker[0] !== "/" || /[\x00-\x1f\x7f]/.test(marker)) {
            console.warn("Wysun Lock: sin marcador de disponibilidad; la sesión sigue bloqueada.");
            return;
        }
        readyProcess.command = ["/bin/sh", "-c", "umask 077; printf '%s' locked > \"$1\"", "sh", marker];
        readyProcess.running = true;
    }

    function unlockNow(): void {
        if (!lock.secure || !lock.locked)
            return;
        auth.abort();
        lock.locked = false;
        unlockWatch.start();
    }

    // The refinement terminal always wears the Severance palette (severance-scheme.json), whatever the
    // desktop colours: teal glass, cyan phosphor, coloured tempers.
    LockPalette {
        id: colours
        path: Quickshell.shellPath("modules/lockscreen/severance-scheme.json")
    }

    WlSessionLock {
        id: lock

        locked: true

        WlSessionLockSurface {
            id: surface

            readonly property bool primary: surface.screen !== null && surface.screen.name === root.output
            color: primary ? colours.surface : Qt.darker(colours.surface, 2.5)

            Loader {
                anchors.fill: parent
                active: surface.primary
                focus: surface.primary
                sourceComponent: LockScene {
                    id: mainScene
                    scheme: colours
                    authState: auth.state
                    detail: auth.detail
                    leaving: root.leaving
                    username: root.username
                    mono: Tokens.font.mono.small.family
                    shaderDir: root.shaderDir
                    reducedMotion: root.reducedMotion
                    exitStyle: "elevator"
                    desktop: root.desktop.length > 0 ? "file://" + root.desktop : ""
                    onSubmitted: password => auth.submit(password)
                    Component.onCompleted: root.scene = mainScene
                }
            }

            // The other monitors: dark, but typing there still reaches the scene.
            Item {
                anchors.fill: parent
                visible: !surface.primary
                focus: !surface.primary
                Keys.onPressed: event => {
                    if (root.scene)
                        root.scene.relay(event);
                    event.accepted = true;
                }
            }
        }
    }

    LockAuth {
        id: auth

        secure: lock.secure
        configDirectory: Quickshell.shellPath("assets/pam.d")
        onAuthenticated: granted.start()
    }

    // Accepted: let the refinement complete and the elevator doors close, then unlock.
    Timer {
        id: granted
        interval: root.reducedMotion ? 0 : 1300
        onTriggered: {
            root.leaving = true;
            powerOff.start();
        }
    }
    Timer {
        id: powerOff
        interval: root.reducedMotion ? 0 : (root.scene ? root.scene.leaveDuration : 1400) + 100
        onTriggered: root.unlockNow()
    }

    Connections {
        target: lock
        function onSecureStateChanged(): void {
            if (lock.secure)
                root.markReady();
        }
        function onLockStateChanged(): void {
            if (!lock.locked)
                quitTimer.start();
        }
    }

    // If the compositor never confirms the lock, exit non-zero so wysun-lock can fall back to
    // swaylock instead of pretending the session is protected.
    Timer {
        interval: 15000
        running: !lock.secure
        onTriggered: {
            if (!lock.secure)
                Qt.exit(3);
        }
    }
    Timer {
        id: quitTimer
        interval: 400
        onTriggered: {
            if (root.desktop.length > 0 && root.desktop[0] === "/")
                Quickshell.execDetached(["rm", "-f", "--", root.desktop]);
            Qt.exit(0);
        }
    }
    Timer {
        id: unlockWatch
        interval: 3000
        onTriggered: {
            if (lock.locked) {
                root.leaving = false;
                auth.state = "error";
                auth.detail = "COULD NOT UNLOCK THE SESSION";
            }
        }
    }

    Process {
        id: readyProcess
        onExited: code => {
            if (code !== 0)
                console.warn("Wysun Lock: no se pudo publicar la disponibilidad.");
        }
    }
}
