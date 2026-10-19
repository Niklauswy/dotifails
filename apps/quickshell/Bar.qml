pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "Logic.js" as Logic

PanelWindow {
    id: bar
    required property var preferences
    required property var controller
    required property var clock
    required property var resources
    required property var modelData
    screen: modelData
    readonly property var monitor: Hyprland.monitorFor(modelData)
    readonly property bool fullscreen: monitor?.activeWorkspace?.hasFullscreen ?? false
    readonly property bool compact: width < 1000
    readonly property var presentation: Logic.barPresentation(width)
    visible: Logic.monitorEnabled(preferences.environment, modelData.name, preferences.nativeBarData) && !fullscreen
    anchors { top: true; left: true; right: true }
    margins { top: preferences.bar.offset; left: 12; right: 12 }
    implicitHeight: preferences.bar.height
    exclusiveZone: implicitHeight + preferences.bar.offset
    color: "transparent"
    WlrLayershell.namespace: "wysun-bar"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    Rectangle {
        anchors.fill: parent
        color: bar.preferences.bar.background || Qt.alpha(bar.preferences.palette.background, bar.preferences.appearance.opacity)
        radius: bar.preferences.bar.radius
        border.width: 1
        border.color: Qt.alpha(bar.preferences.bar.accent || bar.preferences.palette.accent, 0.22)
    }
    // Preserve module order and visibility. Overflow scrolls on small outputs.
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 6
        anchors.rightMargin: 6
        spacing: 8
        Repeater {
            model: [bar.preferences.bar.left, bar.preferences.bar.center, bar.preferences.bar.right]
            Flickable {
                id: segment
                required property var modelData
                required property int index
                Layout.fillWidth: index !== 1
                Layout.fillHeight: true
                // Keep the middle centered when both sides fit, and reserve
                // natural control widths before using overflow on small outputs.
                Layout.preferredWidth: index === 1 ? moduleRow.implicitWidth : 1
                Layout.minimumWidth: Math.min(moduleRow.implicitWidth, Math.max(36, bar.width * 0.45))
                contentWidth: moduleRow.implicitWidth
                contentHeight: height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Row {
                    id: moduleRow
                    x: segment.index === 2 ? Math.max(0, segment.width - width) : 0
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Repeater {
                        model: segment.modelData
                        BarModule {
                            required property string modelData
                            kind: modelData
                            barWindow: bar
                            preferences: bar.preferences
                            controller: bar.controller
                            clock: bar.clock
                            resources: bar.resources
                        }
                    }
                }
            }
        }
    }
}
