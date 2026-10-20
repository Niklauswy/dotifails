// Adaptado de caelestia-dots/shell/modules/osd/{Wrapper,Content}.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
// One passive window per output. It never takes keyboard focus or input
// (empty input mask) and only exists visually while the OSD is showing.
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../../" as Wysun
import "../../components" as Components

PanelWindow {
    id: root

    required property var osd
    required property var motion
    required property var modelData

    screen: modelData
    readonly property bool wanted: osd.active && osd.screenName === modelData.name
    property real progress: wanted ? 1 : 0

    visible: wanted || progress > 0.001
    anchors { top: true; bottom: true; right: true }
    implicitWidth: Wysun.Appearance.spaceXl * 16
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    WlrLayershell.namespace: "wysun-osd"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region {}

    Behavior on progress {
        Components.Anim { motion: root.motion; type: Components.Anim.Emphasized }
    }

    OsdContent {
        anchors.right: parent.right
        anchors.rightMargin: Wysun.Appearance.spaceXl
        anchors.verticalCenter: parent.verticalCenter
        width: Math.min(360, Math.max(260, root.width - Wysun.Appearance.spaceXl * 2))
        opacity: root.progress
        transform: Translate { x: root.motion.reducedMotion ? 0 : (1 - root.progress) * Wysun.Appearance.spaceXl }
        motion: root.motion
        mode: root.osd.mode
        volume: root.osd.audio.volume
        muted: root.osd.audio.muted
        sourceVolume: root.osd.audio.sourceVolume
        sourceMuted: root.osd.audio.sourceMuted
        brightness: root.osd.brightness.value
        audioAvailable: root.osd.audio.available
        brightnessAvailable: root.osd.brightness.available
    }
}
