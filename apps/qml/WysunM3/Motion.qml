// Motion kinds and the reduced-motion switch. A kind is "fastSpatial|defaultSpatial|slowSpatial|fastEffects|
// defaultEffects|slowEffects" (the M3 Expressive springs: spatial moves and resizes and may overshoot, effects
// fade colour and opacity and never do) or the name of any anim.curves token ("emphasized", "standard"...).
pragma Singleton
import QtQuick

QtObject {
    readonly property bool reduced: Theme.reducedMotion

    // "fastSpatial" -> "expressiveFastSpatial"; a token name stays as it is.
    function token(kind: string): string {
        if (Theme.anim.curves?.[kind] !== undefined)
            return kind;
        return "expressive" + kind.charAt(0).toUpperCase() + kind.slice(1);
    }

    function ms(kind: string): int {
        return reduced ? 0 : Theme.duration(token(kind));
    }

    function bezier(kind: string): var {
        return Theme.curve(token(kind));
    }
}
