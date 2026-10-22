pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.components.containers
import qs.services

// Wysun's screenshot tool, inside the shell: no extra process, no window to
// focus, so the pointer stays where it is and a repeated shortcut does nothing.
// IPC (`wysun-shell screenshot …`):
//   picker screenshot <mode> <saveDir> <autoSave>   mode: actions | annotate
//   picker region "X,Y WxH"   select a region of the open picker
//   picker accept             copy (and save) it, as Enter does
//   picker close
Scope {
    id: root

    property Session session: null

    signal acceptRequested

    function open(mode: string, saveDir: string, autoSave: bool): bool {
        // Already open: a repeated shortcut is simply ignored.
        if (session || pointer.running)
            return false;
        pointer.request = { mode: mode === "annotate" ? "annotate" : "actions", saveDir: saveDir, autoSave: autoSave };
        pointer.running = true;
        return true;
    }

    function start(request: var, cursor: point): void {
        // Panels opened by hover or shortcut close, and the drawers stop reacting to hover.
        for (const screen of Quickshell.screens) {
            const state = ShellState.forScreen(screen);
            if (!state)
                continue;
            state.dashboard = state.aiUsage = state.utilities = state.sidebar = state.osd = state.session = state.launcher = false;
        }
        ShellState.capturing = true;
        const output = Quickshell.screens.find(s => cursor.x >= s.x && cursor.x < s.x + s.width && cursor.y >= s.y && cursor.y < s.y + s.height) ?? Quickshell.screens[0];
        session = sessionComponent.createObject(root, {
            mode: request.mode,
            saveDir: request.saveDir ?? "",
            autoSave: request.autoSave,
            screenName: output?.name ?? ""
        });
        windows.cursor = cursor;
        windows.active = true;
    }

    // Selects a region of the open picker from global "X,Y WxH" (slurp/grim -g format).
    function selectRegion(geometry: string): bool {
        const m = /^(-?\d+),(-?\d+) (\d+)x(\d+)$/.exec(geometry.trim());
        if (!session || !m)
            return false;
        const [x, y, w, h] = m.slice(1).map(Number);
        const output = Quickshell.screens.find(s => x >= s.x && x < s.x + s.width && y >= s.y && y < s.y + s.height);
        if (!output)
            return false;
        session.screenName = output.name;
        session.selection = Qt.rect(x - output.x, y - output.y, Math.min(w, output.x + output.width - x), Math.min(h, output.y + output.height - y));
        session.phase = session.mode === "annotate" ? "edit" : "actions";
        return true;
    }

    function accept(): bool {
        if (!session || session.phase === "select")
            return false;
        acceptRequested();
        return true;
    }

    function close(): void {
        windows.active = false;
        ShellState.capturing = false;
        session?.destroy();
        session = null;
    }

    Component {
        id: sessionComponent

        Session {
            onFinished: root.close()
        }
    }

    // Where the pointer is, so the selection starts on that output.
    Process {
        id: pointer

        property var request

        command: ["hyprctl", "cursorpos", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                let cursor = Qt.point(0, 0);
                try {
                    const pos = JSON.parse(text);
                    cursor = Qt.point(pos.x, pos.y);
                } catch (error) {
                    console.warn("Screenshot: unknown pointer position", error);
                }
                root.start(pointer.request, cursor);
            }
        }
    }

    LazyLoader {
        id: windows

        property point cursor

        Variants {
            model: Screens.screens

            StyledWindow {
                id: win

                required property ShellScreen modelData
                readonly property bool owner: root.session?.screenName === modelData.name

                screen: modelData
                name: "area-picker"
                color: "transparent"
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.keyboardFocus: owner ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                Picker {
                    id: picker

                    session: root.session
                    screen: win.modelData
                    pointer: Qt.point(windows.cursor.x - win.modelData.x, windows.cursor.y - win.modelData.y)
                }

                Connections {
                    function onAcceptRequested(): void {
                        if (picker.active)
                            picker.deliver(root.session.autoSave);
                    }

                    target: root
                }
            }
        }
    }

    IpcHandler {
        function screenshot(mode: string, saveDir: string, autoSave: string): bool {
            return root.open(mode, saveDir, autoSave !== "false" && autoSave !== "0");
        }

        // Older entry points.
        function open(): void {
            root.open("actions", "", true);
        }

        function openFreeze(): void {
            root.open("actions", "", true);
        }

        function openClip(): void {
            root.open("actions", "", false);
        }

        function openFreezeClip(): void {
            root.open("actions", "", false);
        }

        function region(geometry: string): bool {
            return root.selectRegion(geometry);
        }

        // Copies (and saves) the current selection, as Enter does.
        function accept(): bool {
            return root.accept();
        }

        // Recovery path: the picker holds exclusive keyboard focus, so it must be
        // closable without a key press inside it.
        function close(): void {
            root.close();
        }

        target: "picker"
    }
}
