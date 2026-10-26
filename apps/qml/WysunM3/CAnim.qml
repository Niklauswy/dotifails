// ColorAnimation with the M3 Expressive spring of its `kind` (see Motion and Anim).
import QtQuick

ColorAnimation {
    id: root

    property string kind: "defaultEffects"
    readonly property bool _reduced: Motion.reduced

    duration: Motion.ms(kind)
    easing.type: Easing.BezierSpline
    easing.bezierCurve: Motion.bezier(kind)

    on_ReducedChanged: {
        if (_reduced && running)
            complete();
    }
}
