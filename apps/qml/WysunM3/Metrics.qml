// Component measures that are not in tokens.json, each one a named M3 component token (material-web
// tokens v0_192, https://github.com/material-components/material-web) so no component carries a bare number.
// Radii, spacing, type and motion come from Theme (tokens.json); only sizes of parts live here.
pragma Singleton
import QtQuick

QtObject {
    // Icons (md-comp-*: icon-size / with-icon-icon-size)
    readonly property int iconSize: 24

    // State layer opacities (md-sys-state)
    readonly property real stateHover: 0.08
    readonly property real stateFocus: 0.12
    readonly property real statePressed: 0.12
    readonly property real stateDragged: 0.16

    // Transition patterns (M3 motion: fade through starts at 92 % scale; shared axis Z scales 80 % <-> 110 %)
    readonly property real fadeThroughScale: 0.92
    readonly property real sharedAxisZSmall: 0.8
    readonly property real sharedAxisZLarge: 1.1

    // Disabled controls: container 10 %, content 38 % of onSurface (md.sys.state / md-comp-*-disabled-*-opacity)
    readonly property real disabledContainer: 0.10
    readonly property real disabledContent: 0.38

    // Focus indicator (md.sys.state.focus-indicator): 3 dp thick, 2 dp outside the control
    readonly property int focusRingWidth: 3
    readonly property int focusRingOffset: 2

    // Surface tint by elevation level 0-5 (md.sys.elevation: 0, 5, 8, 11, 12, 14 %)
    readonly property var elevationTint: [0, 0.05, 0.08, 0.11, 0.12, 0.14]

    readonly property real disabledOutline: 0.12
    // Raised surfaces: stacked translucent layers of the shadow colour (no effects module needed)
    readonly property real shadowLayerOpacity: 0.06

    // Buttons (md-comp-filled-button & co.): container height 40, icon 18, leading/trailing space 24 (16 next to an
    // icon), text button 12; outlines are 1 dp
    readonly property int buttonHeight: 40
    readonly property int buttonIconSize: 18
    readonly property int buttonPadding: 24
    readonly property int buttonPaddingWithIcon: 16
    readonly property int textButtonPadding: 12
    readonly property int outlineWidth: 1

    // Icon button (md-comp-icon-button): 40 target, 24 icon
    readonly property int iconButtonSize: 40

    // FAB (md-comp-fab*): small 40, regular 56, large 96 (icon 36); extended 56 high, 16 leading, 20 trailing
    readonly property int fabSmall: 40
    readonly property int fabRegular: 56
    readonly property int fabLarge: 96
    readonly property int fabLargeIconSize: 36
    readonly property int fabExtendedLeading: 16
    readonly property int fabExtendedTrailing: 20
    readonly property int fabElevation: 3

    // Segmented button (md-comp-outlined-segmented-button): 40 high, 18 icon, 1 dp outline
    readonly property int segmentedHeight: 40
}
