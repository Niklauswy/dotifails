// Test harness: the production GreeterRoot, driven like the keyboard would (wrong, then right
// password) against tests/fake_greetd.py. Snapshots the primary screen at each step when asked.
import QtQuick
import Quickshell
import "../apps/shell/modules/lockscreen"

ShellRoot {
    GreeterRoot {
        id: greeter
    }

    Timer {
        id: script

        property int step: 0
        readonly property var steps: [
            [2500, () => greeter.submit("wrong-password")],
            [1200, () => {}],
            [2600, () => greeter.navigate("session")],
            [600, () => greeter.navigate("session")],
            [600, () => greeter.submit("wysun")],
            [1500, () => {}],
            [700, () => {}]
        ]
        interval: steps[0][0]
        running: true
        onTriggered: {
            steps[step][1]();
            console.log("harness step", step, greeter.authState, greeter.user, greeter.session ? greeter.session.name : "");
            step++;
            if (step < steps.length) {
                interval = steps[step][0];
                restart();
            }
        }
    }
}
