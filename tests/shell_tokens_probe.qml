// Prints what the shell plugin made of wysun/theme/tokens.json (see tests/test_shell_tokens.py).
import QtQuick
import Wysun.Config

QtObject {
    Component.onCompleted: {
        const appearance = GlobalConfig.appearance;
        console.info("TOKENS " + JSON.stringify({
            roundingSmall: appearance.rounding.small,
            roundingMedium: appearance.rounding.medium,
            spacingLarge: appearance.spacing.large,
            paddingMedium: appearance.padding.medium,
            durationNormal: appearance.anim.durations.normal,
            curveStandard: TokenConfig.appearance.curves.standard
        }));
        Qt.quit();
    }
}
