// Prints what the live annotation toolbar offers while recording and what its pause and stop buttons emit (see
// tests/test_shell_recording.py). The test runs it as the shell.qml of a throwaway shell dir that holds
// services/Colours.qml, a Wallpapers stub, utils/, components/ and modules/areapicker/.
import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.modules.areapicker

ShellRoot {
    FloatingWindow {
        id: win

        implicitWidth: 900
        implicitHeight: 400

        function find(item, name) {
            if (item.objectName === name)
                return item;
            for (const child of item.children) {
                const found = win.find(child, name);
                if (found)
                    return found;
            }
            return null;
        }

        function describe(bar) {
            const out = {};
            for (const name of ["pauseRecording", "stopRecording"]) {
                const tool = win.find(bar, name);
                out[name] = tool ? { visible: tool.visible, icon: tool.icon, hint: tool.hint } : null;
            }
            return out;
        }

        ColumnLayout {
            anchors.fill: parent

            Annotations {
                id: marks

                Layout.preferredWidth: 10
                Layout.preferredHeight: 10
            }
            EditorToolbar {
                id: live

                live: true
                annotations: marks
                onStop: console.info("SIGNAL stop")
                onPause: console.info("SIGNAL pause")
                onCancel: console.info("SIGNAL cancel")
            }
            EditorToolbar {
                id: paused

                live: true
                paused: true
                annotations: marks
            }
            EditorToolbar {
                id: capture

                annotations: marks
            }
        }

        Timer {
            interval: 1500
            running: true
            onTriggered: {
                console.info("BAR " + JSON.stringify({ live: win.describe(live), paused: win.describe(paused), capture: win.describe(capture) }));
                for (const name of ["pauseRecording", "stopRecording"]) {
                    const tool = win.find(live, name);
                    if (tool)
                        tool.clicked();
                }
                Qt.quit();
            }
        }
    }
}
