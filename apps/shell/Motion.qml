import QtQuick

QtObject {
    required property bool reducedMotion

    readonly property int enter: reducedMotion ? 0 : Appearance.motionExit + Appearance.motionFast / 2
    readonly property int exit: reducedMotion ? 0 : Appearance.motionExit
    readonly property int hover: reducedMotion ? 0 : Appearance.motionFast
    readonly property int morph: reducedMotion ? 0 : Appearance.motionEnter + Appearance.spaceL + Appearance.spaceXs
    readonly property int reducedFade: Appearance.motionFast / 2
    readonly property var standardCurve: [0.2, 0, 0, 1, 1, 1]
    readonly property var emphasizedCurve: [0.05, 0, 2 / 15, 0.06, 1 / 6, 0.4, 5 / 24, 0.82, 0.25, 1, 1, 1]

    function effectsDuration(normal) { return reducedMotion ? reducedFade : normal; }
}
