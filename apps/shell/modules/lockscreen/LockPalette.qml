// Colours of the lock, read straight from the shell's scheme contract (~/.local/state/wysun/scheme.json).
// The lock is its own process: it must not load the shell services (notification server, audio,
// network…). Until the scheme is read, or if it is missing, the platform palette stands in.
import QtQuick
import Quickshell
import Quickshell.Io

Scope {
    id: root

    property string path: (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/wysun/scheme.json"
    property var colours: ({})

    function pick(name: string, fallback: color): color {
        const value = colours[name];
        return typeof value === "string" && /^[0-9a-fA-F]{6}$/.test(value) ? "#" + value : fallback;
    }

    readonly property color surface: pick("surface", system.window)
    readonly property color primary: pick("primary", system.highlight)
    readonly property color error: pick("error", system.highlight)
    readonly property color text: pick("onSurface", system.windowText)
    readonly property color muted: pick("onSurfaceVariant", system.placeholderText)

    SystemPalette {
        id: system
    }

    FileView {
        path: root.path
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const scheme = JSON.parse(text());
                root.colours = scheme && typeof scheme.colours === "object" ? scheme.colours : {};
            } catch (error) {
                root.colours = {};
            }
        }
    }
}
