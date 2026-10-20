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

    function apply(spec, selection) { tokens = Logic.resolveTheme(spec, selection.style, selection.variant); }

    function colorOf(name) { return Logic.qmlColor(tokens[name]); }
    function numberOf(name, fallback) { return Logic.tokenNumber(tokens, name, fallback); }

    readonly property string style: tokens.style || ""
    readonly property string variant: tokens.variant || ""
    readonly property string name: tokens.name || ""
    readonly property string wallpaper: tokens.wallpaper || ""
    readonly property bool translucent: tokens.translucent !== false
    readonly property bool light: tokens.material === "pearl"

    // Surfaces and lines
    readonly property color canvas: colorOf("canvas")
    readonly property color surface: colorOf("surface")
    readonly property color surfaceRaised: colorOf("surface_raised")
    readonly property color well: colorOf("well")
    readonly property color fill: colorOf("fill")
    readonly property color line: colorOf("line")
    readonly property color lineStrong: colorOf("line_strong")
    readonly property color scrim: colorOf("scrim")
    // Text
    readonly property color text: colorOf("text")
    readonly property color textStrong: colorOf("text_strong")
    readonly property color muted: colorOf("muted")
    readonly property color disabled: colorOf("disabled")
    // Interaction
    readonly property color accent: colorOf("accent")
    readonly property color accentHover: colorOf("accent_hover")
    readonly property color accentPressed: colorOf("accent_pressed")
    readonly property color onAccent: colorOf("on_accent")
    readonly property color selection: colorOf("selection")
    readonly property color selectionText: colorOf("selection_text")
    readonly property color selectionLine: colorOf("selection_line")
    readonly property color hover: colorOf("hover")
    readonly property color pressed: colorOf("pressed")
    readonly property color focus: colorOf("focus")
    // State colours
    readonly property color danger: colorOf("danger")
    readonly property color success: colorOf("success")
    readonly property color warning: colorOf("warning")
    // Window material (glass for Space Black, pearl/mica for Fluent)
    readonly property color materialTop: colorOf("material_top")
    readonly property color materialMid: colorOf("material_mid")
    readonly property color materialBottom: colorOf("material_bottom")
    readonly property color materialEdge: colorOf("material_edge")
    readonly property color materialHighlight: colorOf("material_highlight")

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

    // Typography
    readonly property var installedFamilies: Qt.fontFamilies()
    readonly property string fontFamily: Logic.tokenFont(tokens, installedFamilies)
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
