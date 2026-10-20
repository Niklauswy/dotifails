import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import "modules/background" as BackgroundModule

PanelWindow {
    id: desktop
    required property var preferences
    required property var modelData
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    color: Appearance.canvas
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.namespace: "wysun-desktop"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    // A wallpaper never consumes desktop clicks or keyboard focus.
    mask: Region {}
    // Each delegate observes only its own output. Variants destroys it on unplug.
    readonly property var monitor: Hyprland.monitorFor(modelData)
    BackgroundModule.Background {
        anchors.fill: parent
        preferences: desktop.preferences
        outputName: desktop.modelData.name
        pixelRatio: desktop.modelData.devicePixelRatio
        fullscreen: desktop.monitor?.activeWorkspace?.hasFullscreen === true
    }
}
