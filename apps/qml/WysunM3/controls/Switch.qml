// M3 switch: a 52 x 32 track and a handle that grows when it is on or pressed. A click, Space or Enter flips
// `checked` and emits toggled(); the 40 dp state layer surrounds the handle, not the track. Use it for a setting
// that applies at once (on/off); for one of several values use SegmentedButtons or Dropdown.
import QtQuick
import WysunM3

ButtonBase {
    id: root

    readonly property real handleSize: pressed ? Metrics.switchHandlePressed : checked ? Metrics.switchHandleOn : Metrics.switchHandleOff
    readonly property bool _lit: hovered || pressed

    checkable: true
    morph: false
    implicitWidth: Metrics.switchTrackWidth
    implicitHeight: Metrics.switchTrackHeight
    width: implicitWidth
    height: implicitHeight
    containerColor: checked ? Theme.m3primary : Theme.m3surfaceContainerHighest
    outline: checked ? 0 : Metrics.switchOutline
    outlineColor: Theme.m3outline
    // The state layer of a switch is the circle around the handle (drawn below), not a veil over the track.
    stateLayer.tint: "transparent"

    Item {
        id: slot

        z: 2
        width: Metrics.switchStateLayer
        height: width
        x: (root.checked ? root.width - root.height / 2 : root.height / 2) - width / 2
        y: (root.height - height) / 2

        SpringBehavior on x {
            kind: "fastSpatial"
        }

        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: root.checked ? Theme.m3primary : Theme.m3onSurface
            opacity: root.disabled ? 0 : root.pressed ? Theme.stateOpacity("pressed") : root.activeFocus ? Theme.stateOpacity("focus") : root.hovered ? Theme.stateOpacity("hover") : 0
        }

        Rectangle {
            anchors.centerIn: parent
            width: root.handleSize
            height: width
            radius: width / 2
            color: root.disabled ? (root.checked ? Theme.m3surface : Qt.alpha(Theme.m3onSurface, Metrics.disabledContent)) : root.checked ? (root._lit ? Theme.m3primaryContainer : Theme.m3onPrimary) : (root._lit ? Theme.m3onSurfaceVariant : Theme.m3outline)

            SpringBehavior on width {
                kind: "fastSpatial"
            }
        }
    }
}
