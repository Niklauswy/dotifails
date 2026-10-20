pragma Singleton
import QtQuick
import "Logic.js" as Logic

// Semantic theme tokens for every Wysun shell widget. The values come from
// wysun_theme.json (the same file Qt, Recorder and Screenshot use) and are
// pushed here by Preferences whenever theme.json changes, so a style or
// variant switch repaints the bar, panels and any new widget live.
//
// A theme-aware widget only does `color: Appearance.surface`; it never writes a
// colour, radius, font size or duration of its own.
QtObject {
    id: root

    // Flat token map (see Logic.resolveTheme). Empty until the first load.
    property var tokens: ({})
    property var dynamicPalette: ({})
    property bool dynamicActive: false
    property string dynamicMode: ""
    property int fontEpoch: 0

    function apply(spec, selection) { tokens = Logic.resolveTheme(spec, selection.style, selection.variant); }
    function applyScheme(roles, mode, active) {
        dynamicPalette = roles && typeof roles === "object" ? roles : {};
        dynamicMode = mode || "";
        dynamicActive = active === true;
    }
    function refreshFonts() { fontEpoch++; }

    function colorOf(name) { return Logic.qmlColor(tokens[name]); }
    function roleColor(role, token, fallback) {
        var value = dynamicPalette && dynamicPalette[role];
        return value ? value : colorOf(token) || fallback;
    }
    function numberOf(name, fallback) { return Logic.tokenNumber(tokens, name, fallback); }

    readonly property string style: tokens.style || ""
    readonly property string variant: tokens.variant || ""
    readonly property string name: tokens.name || ""
    readonly property string wallpaper: tokens.wallpaper || ""
    readonly property bool translucent: tokens.translucent !== false
    readonly property bool light: dynamicActive ? dynamicMode === "light" : tokens.material === "pearl"

    // theme-exception-begin: transparent fallbacks apply only before Wysun's fixed or dynamic theme loads
    // Surfaces and lines
    readonly property color canvas: roleColor("background", "canvas", "#00000000")
    readonly property color surface: roleColor("surface", "surface", "#00000000")
    readonly property color surfaceRaised: roleColor("surfaceContainerHigh", "surface_raised", "#00000000")
    readonly property color well: roleColor("surfaceContainerLow", "well", "#00000000")
    readonly property color fill: colorOf("fill")
    readonly property color line: roleColor("outlineVariant", "line", "#00000000")
    readonly property color lineStrong: roleColor("outline", "line_strong", "#00000000")
    readonly property color scrim: roleColor("scrim", "scrim", "#00000000")
    // Text
    readonly property color text: roleColor("onSurface", "text", "#00000000")
    readonly property color textStrong: roleColor("onBackground", "text_strong", "#00000000")
    readonly property color muted: roleColor("onSurfaceVariant", "muted", "#00000000")
    readonly property color disabled: colorOf("disabled")
    // Interaction
    readonly property color accent: roleColor("primary", "accent", "#00000000")
    readonly property color accentHover: colorOf("accent_hover")
    readonly property color accentPressed: colorOf("accent_pressed")
    readonly property color onAccent: roleColor("onPrimary", "on_accent", "#00000000")
    readonly property color selection: roleColor("primaryContainer", "selection", "#00000000")
    readonly property color selectionText: roleColor("onPrimaryContainer", "selection_text", "#00000000")
    readonly property color selectionLine: colorOf("selection_line")
    readonly property color hover: colorOf("hover")
    readonly property color pressed: colorOf("pressed")
    readonly property color focus: roleColor("primary", "focus", "#00000000")
    // State colours
    readonly property color danger: roleColor("error", "danger", "#00000000")
    readonly property color success: colorOf("success")
    readonly property color warning: colorOf("warning")
    // Window material (glass for Space Black, pearl/mica for Fluent)
    readonly property color materialTop: roleColor("surfaceContainerLow", "material_top", "#00000000")
    readonly property color materialMid: roleColor("surfaceContainer", "material_mid", "#00000000")
    readonly property color materialBottom: roleColor("surfaceContainerHigh", "material_bottom", "#00000000")
    readonly property color materialEdge: roleColor("outlineVariant", "material_edge", "#00000000")
    readonly property color materialHighlight: roleColor("outline", "material_highlight", "#00000000")
    // theme-exception-end

    // Shape
    readonly property real radiusS: numberOf("radius_s", 8)
    readonly property real radiusControl: numberOf("radius_control", 10)
    readonly property real radiusM: numberOf("radius_m", 12)
    readonly property real radiusL: numberOf("radius_l", 20)
    readonly property real spaceXs: numberOf("space_xs", 4)
    readonly property real spaceS: numberOf("space_s", 8)
    readonly property real spaceM: numberOf("space_m", 12)
    readonly property real spaceL: numberOf("space_l", 16)
    readonly property real spaceXl: numberOf("space_xl", 24)
    readonly property real borderWidth: numberOf("border", 1)
    readonly property real focusWidth: numberOf("focus_width", 1)
    readonly property real railWidth: numberOf("space_xl", 24) * 3
    readonly property real frameInset: numberOf("space_s", 8) + numberOf("space_m", 12) / 2
    readonly property real frameThickness: numberOf("space_xs", 4) * 2.5
    readonly property real frameRadius: numberOf("radius_l", 20) + numberOf("space_s", 8) / 2

    // Typography
    readonly property var installedFamilies: { fontEpoch; return Qt.fontFamilies(); }
    readonly property string fontFamily: installedFamilies.indexOf("Rubik") >= 0 ? "Rubik" : Logic.tokenFont(tokens, installedFamilies)
    readonly property string iconFontFamily: installedFamilies.indexOf("Material Symbols Rounded") >= 0 ? "Material Symbols Rounded" : "Sans Serif"
    readonly property int fontCaption: numberOf("font_caption", 10)
    readonly property int fontSmall: numberOf("font_small", 11)
    readonly property int fontBody: numberOf("font_body", 13)
    readonly property int fontHeading: numberOf("font_heading", 16)
    readonly property int fontTitle: numberOf("font_title", 23)

    // Motion (milliseconds); Preferences.appearance.reducedMotion still wins
    readonly property int motionEnter: numberOf("motion_enter", 200)
    readonly property int motionExit: numberOf("motion_exit", 160)
    readonly property int motionFast: numberOf("motion_fast", 120)

    // Opacity of window material: the user's preference for glass, solid for Fluent
    function materialAlpha(preference) { return Logic.surfaceOpacity(tokens, preference); }
}
