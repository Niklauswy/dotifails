// NumberAnimation with the M3 Expressive spring of its `kind` (see Motion). With reduced motion it takes no
// time, and one that is already running jumps to its destination.
import QtQuick

NumberAnimation {
    id: root

    property string kind: "defaultSpatial"
    readonly property bool _reduced: Motion.reduced

    duration: Motion.ms(kind)
    easing.type: Easing.BezierSpline
    easing.bezierCurve: Motion.bezier(kind)

    on_ReducedChanged: {
        if (_reduced && running)
            complete();
    }
}
