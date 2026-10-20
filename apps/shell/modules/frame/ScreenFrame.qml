// Adaptado de caelestia-dots/shell/modules/drawers/ContentWindow.qml y Exclusions.qml
// (GPL-3.0), modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "../../Logic.js" as Logic
import "../../" as Wysun

PanelWindow {
    id: frame
    required property var preferences
    required property var outputs
    required property var modelData
    screen: modelData
    readonly property bool fullscreen: outputs.isFullscreen(modelData)

    visible: Logic.monitorEnabled(preferences.environment, modelData.name, preferences.nativeBarData) && preferences.shell.frameEnabled && !fullscreen
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    WlrLayershell.namespace: "wysun-frame"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region {}

    Rectangle {
        anchors.fill: parent
        anchors.margins: Wysun.Appearance.frameInset
        color: "transparent"
        radius: Wysun.Appearance.frameRadius
        border.width: Wysun.Appearance.frameThickness
        border.color: Wysun.Appearance.materialEdge
        antialiasing: true
    }
}
