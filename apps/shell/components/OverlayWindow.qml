import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import qs.components.containers
import qs.services

// A full-attention layer on one screen: opened by a ScreenState flag (`wysunShell toggle <surface>`),
// it takes the keyboard on demand and closes with Escape or a click outside it.
StyledWindow {
    id: root

    required property ShellScreen modelData
    readonly property ScreenState state: ShellState.forScreen(modelData)
    // ScreenState flag that opens it; "" keeps it open for as long as the window exists.
    property string surface
    readonly property bool open: surface ? root.state[surface] : true
    property bool active: open
    property int openAnim: Anim.DefaultSpatial
    property int closeAnim: Anim.DefaultSpatial
    // 0 → 1 while opening and back while closing; contents animate from it.
    property real reveal: active ? 1 : 0
    property bool closeOnEscape: true
    property bool focusGrab: active

    signal dismissed()

    function close(): void {
        if (surface)
            root.state[surface] = false;
        else
            dismissed();
    }

    name: surface
    screen: modelData
    Tokens.screen: modelData.name
    visible: active || reveal > 0.001
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: active ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

    Behavior on reveal {
        Anim {
            type: root.active ? root.openAnim : root.closeAnim
        }
    }

    Shortcut {
        sequence: "Escape"
        enabled: root.active && root.closeOnEscape
        onActivated: root.close()
    }

    HyprlandFocusGrab {
        active: root.focusGrab
        windows: [root]
        onCleared: root.close()
    }
}
