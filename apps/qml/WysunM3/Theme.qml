// The shared theme. The host feeds it the wallpaper's Material roles (scheme.json) and the shape, type and motion
// tokens (tokens.json) through ThemeFeed; every colour is a direct M3 role named m3<role> (QML would read a bare
// `onSurface` as a signal handler). Nothing here knows about the shell or Python.
pragma Singleton
import QtQuick

QtObject {
    id: root

    // Fed by the host: {mode: "light"|"dark", colours: {role: "rrggbb"}} and the tokens document.
    property var scheme: ({})
    property var tokens: ({})
    property bool reducedMotion: false

    readonly property string style: "material3"
    property string mode: "dark"
    property var colours: ({})
    readonly property bool dark: mode === "dark"

    // A scheme that is not a complete object is ignored: the last good one keeps painting.
    onSchemeChanged: {
        const s = scheme;
        if (s && typeof s === "object" && s.colours && typeof s.colours === "object" && Object.keys(s.colours).length > 0) {
            colours = s.colours;
            if (s.mode === "light" || s.mode === "dark")
                mode = s.mode;
        }
    }

    // The base palette of the mode fills every role the scheme lacks.
    readonly property var base: tokens.palettes?.[mode]?.scheme ?? ({})
    property var _warned: ({})

    function role(name: string): color {
        const hex = colours[name] ?? base[name];
        if (typeof hex === "string" && hex.length >= 6)
            return "#" + hex;
        if (tokens.palettes && !_warned[name]) {
            _warned[name] = true;
            console.warn("WysunM3: no colour for the role " + name);
        }
        return "transparent";
    }

    readonly property color m3background: role("background")
    readonly property color m3onBackground: role("onBackground")
    readonly property color m3surface: role("surface")
    readonly property color m3surfaceDim: role("surfaceDim")
    readonly property color m3surfaceBright: role("surfaceBright")
    readonly property color m3surfaceContainerLowest: role("surfaceContainerLowest")
    readonly property color m3surfaceContainerLow: role("surfaceContainerLow")
    readonly property color m3surfaceContainer: role("surfaceContainer")
    readonly property color m3surfaceContainerHigh: role("surfaceContainerHigh")
    readonly property color m3surfaceContainerHighest: role("surfaceContainerHighest")
    readonly property color m3onSurface: role("onSurface")
    readonly property color m3surfaceVariant: role("surfaceVariant")
    readonly property color m3onSurfaceVariant: role("onSurfaceVariant")
    readonly property color m3outline: role("outline")
    readonly property color m3outlineVariant: role("outlineVariant")
    readonly property color m3inverseSurface: role("inverseSurface")
    readonly property color m3inverseOnSurface: role("inverseOnSurface")
    readonly property color m3inversePrimary: role("inversePrimary")
    readonly property color m3shadow: role("shadow")
    readonly property color m3scrim: role("scrim")
    readonly property color m3surfaceTint: role("surfaceTint")
    readonly property color m3primary: role("primary")
    readonly property color m3onPrimary: role("onPrimary")
    readonly property color m3primaryContainer: role("primaryContainer")
    readonly property color m3onPrimaryContainer: role("onPrimaryContainer")
    readonly property color m3secondary: role("secondary")
    readonly property color m3onSecondary: role("onSecondary")
    readonly property color m3secondaryContainer: role("secondaryContainer")
    readonly property color m3onSecondaryContainer: role("onSecondaryContainer")
    readonly property color m3tertiary: role("tertiary")
    readonly property color m3onTertiary: role("onTertiary")
    readonly property color m3tertiaryContainer: role("tertiaryContainer")
    readonly property color m3onTertiaryContainer: role("onTertiaryContainer")
    readonly property color m3error: role("error")
    readonly property color m3onError: role("onError")
    readonly property color m3errorContainer: role("errorContainer")
    readonly property color m3onErrorContainer: role("onErrorContainer")
    readonly property color m3success: role("success")
    readonly property color m3onSuccess: role("onSuccess")
    readonly property color m3successContainer: role("successContainer")
    readonly property color m3onSuccessContainer: role("onSuccessContainer")

    // Shape, spacing and motion tokens (the shell's own names).
    readonly property var rounding: tokens.rounding ?? ({})
    readonly property var spacing: tokens.spacing ?? ({})
    readonly property var padding: tokens.padding ?? ({})
    readonly property var anim: tokens.anim ?? ({ curves: {}, durations: {} })
    readonly property var font: tokens.font ?? ({})
    readonly property string iconFamily: tokens.font?.family?.icon ?? ""

    function curve(name: string): var {
        return anim.curves?.[name] ?? anim.curves?.standard ?? [];
    }

    function duration(name: string): int {
        return anim.durations?.[name] ?? anim.durations?.normal ?? 0;
    }

    // "body.medium" -> {family, pointSize, weight}; an unknown role is body.medium.
    function typeFont(role: string): var {
        const parts = String(role).split(".");
        const entry = font[parts[0]]?.[parts[1]] ?? font.body?.medium ?? ({});
        return {
            family: font.family?.sans ?? "",
            pointSize: entry.size ?? 0,
            weight: entry.weight ?? Font.Normal
        };
    }

    // A full (pill) radius for a given height; the token's own value is a huge sentinel.
    function fullRadius(height: real): real {
        return height / 2;
    }

    function stateOpacity(kind: string): real {
        switch (kind) {
        case "hover":
            return Metrics.stateHover;
        case "focus":
            return Metrics.stateFocus;
        case "pressed":
            return Metrics.statePressed;
        case "dragged":
            return Metrics.stateDragged;
        }
        return 0;
    }

    property var _fonts: ({})
    function fontAvailable(family: string): bool {
        if (!(family in _fonts))
            _fonts[family] = family !== "" && Qt.fontFamilies().indexOf(family) >= 0;
        return _fonts[family];
    }
}
