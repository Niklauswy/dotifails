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
}
