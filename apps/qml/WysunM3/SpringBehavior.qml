// A Behavior that animates with the M3 Expressive spring of its `kind` (see Motion): `SpringBehavior on x { kind: "fastSpatial" }`.
// With reduced motion the value just changes, and one that is mid-flight jumps to its destination (complete() does
// not reach animations owned by a Behavior, so this does it from the Behavior's targetValue; a disabled Behavior
// stops its running animation when the value is written).
import QtQuick

Behavior {
    id: root

    property string kind: "defaultSpatial"
    readonly property bool _reduced: Motion.reduced

    on_ReducedChanged: {
        if (_reduced && spring.running) {
            const target = targetProperty;
            enabled = false;
            target.object[target.name] = targetValue;
            enabled = true;
        }
    }

    animation: PropertyAnimation {
        id: spring

        duration: Motion.ms(root.kind)
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Motion.bezier(root.kind)
    }
}
