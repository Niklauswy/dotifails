// The M3 focus indicator: a 3 px ring 2 px outside the control, only while the control has (keyboard) focus.
// Controls are focusPolicy: Qt.TabFocus, so a mouse click never focuses them and never shows the ring.
import QtQuick

Rectangle {
    id: root

    property Item target: parent
    readonly property real _outset: Metrics.focusRingOffset + Metrics.focusRingWidth

    anchors.fill: target
    anchors.margins: -_outset
    radius: (target?.radius ?? 0) + _outset
    color: "transparent"
    border.width: Metrics.focusRingWidth
    border.color: Theme.m3secondary
    visible: target?.activeFocus ?? false
}
