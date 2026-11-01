pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services

// One per screen, on the overlay layer so it shows over fullscreen apps. Input only reaches the surface.
StyledWindow {
    id: win

    required property ShellScreen modelData
    required property var ui
    readonly property bool main: ui.pillScreen === modelData.name
    readonly property bool shown: ui.mode !== "hidden" || Study.active
    // Keeps the window a moment after closing so the last animation finishes.
    property bool lingering

    onShownChanged: {
        if (!shown) {
            lingering = true;
            lingerTimer.restart();
        }
    }

    screen: modelData
    name: "study"
    visible: shown || lingering
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: main && ui.mode === "setup" ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    anchors.top: true
    anchors.bottom: true
    anchors.left: true
    anchors.right: true
    color: "transparent"
    mask: Region {
        item: win.main && win.ui.mode !== "takeover" ? surface : nothing
    }

    Timer {
        id: lingerTimer

        interval: Tokens.anim.durations.extraLarge
        onTriggered: win.lingering = false
    }

    HyprlandFocusGrab {
        active: win.main && win.ui.mode === "setup"
        windows: [win]
        onCleared: win.ui.close()
    }

    Shortcut {
        sequence: "Escape"
        enabled: win.main && (win.ui.mode === "setup" || win.ui.mode === "summary")
        onActivated: win.ui.close()
    }

    Item {
        id: nothing
    }

    // The setup panel dims what is behind it a little; a break dims it less, to invite looking away.
    Rectangle {
        anchors.fill: parent
        color: Colours.palette.m3scrim
        opacity: !win.main ? 0 : win.ui.mode === "setup" ? 0.32 : win.ui.mode === "study" && (Study.phase === "break" || Study.phase === "ready") ? 0.2 : 0

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }

    Halo {
        anchors.fill: parent
        on: Study.active && win.ui.mode === "study"
        sweepTick: win.ui.sweepTick
        shortSweep: win.ui.shortSweep
    }

    // The other screens only fade the full-screen entry in and out.
    Takeover {
        anchors.fill: parent
        visible: !win.main
        shown: win.ui.mode === "takeover"
        config: win.ui.pending
    }

    Surface {
        id: surface

        visible: win.main
        ui: win.ui
    }
}
