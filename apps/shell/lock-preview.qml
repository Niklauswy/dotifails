// Wysun lock · vista previa. A normal window with the real lock scene and a simulated check: it never
// locks the session, never talks to PAM and never sees a real password. «wysun» is accepted, anything
// else is refused. With WYSUN_LOCK_SNAPSHOT=<dir> it walks every state, saves a PNG of each and quits.
import QtQuick
import Quickshell
import "modules/lockscreen"

ShellRoot {
    id: shell

    readonly property string snapshots: Quickshell.env("WYSUN_LOCK_SNAPSHOT") || ""

    LockPalette {
        id: lockColours
        path: Quickshell.shellPath("modules/lockscreen/severance-scheme.json")
    }

    FloatingWindow {
        id: window

        title: "Wysun Lock · vista previa"
        implicitWidth: Number(Quickshell.env("WYSUN_LOCK_PREVIEW_WIDTH") || 1280)
        implicitHeight: Number(Quickshell.env("WYSUN_LOCK_PREVIEW_HEIGHT") || 800)
        color: scene.base

        LockScene {
            id: scene

            anchors.fill: parent
            scheme: lockColours
            username: Quickshell.env("USER") || "wysun"
            shaderDir: Quickshell.env("WYSUN_LOCK_SHADERS") || ""
            exitStyle: Quickshell.env("WYSUN_LOCK_EXIT") || "elevator"
            // Any image stands in for the desktop the doors open on (WYSUN_LOCK_DESKTOP, a path).
            desktop: Quickshell.env("WYSUN_LOCK_DESKTOP") ? "file://" + Quickshell.env("WYSUN_LOCK_DESKTOP") : ""
            reducedMotion: Quickshell.env("ORBIT_REDUCED_MOTION") === "1"
            detail: shell.snapshots ? "" : "Vista previa · prueba «wysun» · Esc borra"
            onSubmitted: password => {
                scene.authState = "authenticating";
                verdict.accepted = password === "wysun";
                verdict.restart();
            }
            Component.onCompleted: focusInput()
        }

        Timer {
            id: verdict

            property bool accepted
            interval: 1500
            onTriggered: {
                scene.authState = accepted ? "success" : "failed";
                if (accepted)
                    leave.restart();
            }
        }

        Timer {
            id: leave
            interval: 1300
            onTriggered: {
                scene.leaving = true;
                reset.restart();
            }
        }

        // The preview loops: after leaving, the lock comes back.
        Timer {
            id: reset
            interval: scene.leaveDuration + 800
            onTriggered: {
                scene.leaving = false;
                scene.dissolve = 0;
                scene.vanish = 0;
                scene.open = 0;
                scene.authState = "locked";
                scene.focusInput();
            }
        }

        // Snapshot walk: [state, wait ms, action].
        Timer {
            id: walk

            property int step: 0
            readonly property var script: [
                ["idle", 1500, () => {}],
                ["selecting", 600, () => scene.selectTargetForPreview()],
                ["harvest", 300, () => scene.releaseForPreview()],
                ["typing", 700, () => scene.typeForPreview(5)],
                ["quota", 500, () => scene.typeForPreview(14)],
                ["perfect", 1600, () => scene.typeForPreview(70)],
                ["party-wave", 1200, () => {}],
                ["reward", 1500, () => {}],
                ["film-ranges", 2600, () => {}],
                ["film-peak", 5700, () => {}],
                ["film-founder", 3000, () => {}],
                ["film-flight", 3200, () => {}],
                ["film-eagle", 3800, () => {}],
                ["hundred", 4400, () => {}],
                ["verifying", 900, () => { scene.clearForPreview(); scene.typeForPreview(6); scene.authState = "authenticating"; }],
                ["denied", 450, () => scene.authState = "failed"],
                ["granted", 700, () => scene.authState = "success"],
                ["leaving", 1150, () => scene.leaving = true],
                ["opening", 900, () => {}],
                ["revealed", 1400, () => {}]
            ]
            interval: 50
            running: shell.snapshots.length > 0
            onTriggered: {
                if (step >= script.length) {
                    Qt.quit();
                    return;
                }
                const entry = script[step];
                entry[2]();
                stop();
                pause.interval = entry[1];
                pause.name = entry[0];
                pause.restart();
            }
        }

        Timer {
            id: pause

            property string name
            onTriggered: scene.grabToImage(result => {
                result.saveToFile(shell.snapshots + "/" + (walk.step + 1) + "-" + name + ".png");
                walk.step++;
                walk.restart();
            })
        }
    }
}
