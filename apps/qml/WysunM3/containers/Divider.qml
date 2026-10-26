// M3 divider: a 1 px outlineVariant line that groups content in lists and containers. `inset` indents it by
// 16 px at the start ("start") or both ends ("both"); `vertical` turns it into a column separator.
import QtQuick
import WysunM3

Item {
    id: root

    property string inset: "none"            // none | start | both
    property bool vertical
    readonly property real _start: inset === "none" ? 0 : Theme.padding.large ?? 0
    readonly property real _end: inset === "both" ? Theme.padding.large ?? 0 : 0

    implicitWidth: vertical ? Metrics.outlineWidth : 0
    implicitHeight: vertical ? 0 : Metrics.outlineWidth

    Rectangle {
        x: root.vertical ? 0 : root._start
        y: root.vertical ? root._start : 0
        width: root.vertical ? root.width : root.width - root._start - root._end
        height: root.vertical ? root.height - root._start - root._end : root.height
        color: Theme.m3outlineVariant
    }
}
