// Prints what Colours made of tokens.json and scheme.json (see tests/test_shell_tokens.py). The test runs it as
// the shell.qml of a throwaway shell dir that holds services/Colours.qml, a Wallpapers stub and utils/.
import QtQuick
import Quickshell
import qs.services

ShellRoot {
    // Singletons are created on first use: touch Colours now so its files load before the report.
    Component.onCompleted: Colours.light
    Timer {
        interval: 1500
        running: true
        onTriggered: {
            console.info("COLOURS " + JSON.stringify({
                primary: String(Colours.palette.m3primary),
                surface: String(Colours.palette.m3surface),
                light: Colours.light
            }));
            Qt.quit();
        }
    }
}
