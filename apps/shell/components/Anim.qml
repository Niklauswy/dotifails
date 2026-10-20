// Derivado de caelestia-dots/shell/components/Anim.qml (GPL-3.0), modificado para Wysun.
// Fuente: caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick

NumberAnimation {
    enum Type { FastSpatial, DefaultSpatial, SlowSpatial, FastEffects, DefaultEffects, Emphasized }
    property var motion
    property int type: Anim.DefaultSpatial

    duration: {
        if (!motion) return 220;
        switch (type) {
        case Anim.FastSpatial: return motion.reducedMotion ? 0 : 180;
        case Anim.SlowSpatial: return motion.reducedMotion ? 0 : 320;
        case Anim.FastEffects: return motion.effectsDuration(120);
        case Anim.DefaultEffects: return motion.effectsDuration(160);
        case Anim.Emphasized: return motion.reducedMotion ? motion.reducedFade : motion.morph;
        default: return motion.enter;
        }
    }
    easing.type: Easing.BezierSpline
    easing.bezierCurve: type === Anim.Emphasized
        ? (motion ? motion.emphasizedCurve : [0.2, 0, 0, 1, 1, 1])
        : (motion ? motion.standardCurve : [0.2, 0, 0, 1, 1, 1])
}
