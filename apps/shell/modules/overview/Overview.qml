// Adapted from end-4/dots-hyprland overview/Overview.qml (GPL-3.0).
// Source: 2f2a376fdb2ad738bf55f693dd0b474b64bb0ab8; see THIRD_PARTY.md.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.components.containers
import qs.services

Scope {
    Variants {
        model: Quickshell.screens
        LazyLoader {
            id: loader
            required property ShellScreen modelData
            readonly property var state: ShellState.forScreen(modelData)
            active: state?.overview ?? false
            StyledWindow {
                name: "overview"
                screen: loader.modelData
                anchors { top: true; bottom: true; left: true; right: true }
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.keyboardFocus: loader.state?.overviewKeyboard ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
                OverviewWidget { anchors.fill: parent; screen: loader.modelData; screenState: loader.state }
            }
        }
    }
}
