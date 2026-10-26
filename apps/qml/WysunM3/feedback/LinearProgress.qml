// M3 (expressive) linear progress: a 4 px primary indicator, a gap, then the secondaryContainer track ending in a
// stop dot. `value` 0-1 for known progress; `indeterminate` loops while visible (still with reduced motion).
import QtQuick
import WysunM3

Item {
    id: root

    property real value: 0
    property bool indeterminate
    readonly property bool animating: loop.running
    readonly property real _t: Metrics.progressThickness
    readonly property real _gap: Metrics.progressGap
    property real _head: 0                     // indeterminate: 0-1 position of the moving segment's end
    readonly property real _from: indeterminate ? Math.max(0, _head - 0.4) * width : 0
    readonly property real _to: indeterminate ? Math.min(1, _head) * width : Math.max(0, Math.min(1, value)) * width

    implicitHeight: _t
    height: implicitHeight

    // Track before the segment (indeterminate only).
    Rectangle {
        visible: root.indeterminate && width > 0
        width: Math.max(0, root._from - root._gap)
        height: root._t
        radius: height / 2
        color: Theme.m3secondaryContainer
    }

    Rectangle {
        x: root._from
        width: Math.max(0, root._to - root._from)
        height: root._t
        radius: height / 2
        color: Theme.m3primary
        visible: width > 0
    }

    // Track after the indicator.
    Rectangle {
        x: root._to > 0 ? root._to + root._gap : 0
        width: Math.max(0, root.width - x)
        height: root._t
        radius: height / 2
        color: Theme.m3secondaryContainer
        visible: width > 0
    }

    // Stop indicator at the end of a determinate track.
    Rectangle {
        visible: !root.indeterminate && root.value < 1
        x: root.width - width
        width: root._t
        height: root._t
        radius: height / 2
        color: Theme.m3primary
    }

    NumberAnimation {
        id: loop

        target: root
        property: "_head"
        from: 0
        to: 1.4
        duration: Theme.duration("extraLarge") * 2
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Motion.bezier("emphasized")
        loops: Animation.Infinite
        running: root.indeterminate && root.visible && !Motion.reduced
        onRunningChanged: if (!running) root._head = 0.7
    }
}
