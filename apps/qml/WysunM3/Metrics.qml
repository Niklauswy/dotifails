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

    // Chips (md-comp-*-chip): 32 high, 18 icon, 24 avatar; 16 leading/trailing space, 8 next to an icon
    readonly property int chipHeight: 32
    readonly property int chipIconSize: 18
    readonly property int chipAvatarSize: 24
    readonly property int chipPadding: 16
    readonly property int chipPaddingWithIcon: 8

    // Badge (md-comp-badge): small dot 6, large 16 high; counts above the max show "max+"
    readonly property int badgeSmall: 6
    readonly property int badgeLarge: 16
    readonly property int badgeMaxCount: 99

    // Progress indicators (md-comp-*-progress-indicator, expressive): track 4, gap 4, stop dot 4; circular 48
    readonly property int progressThickness: 4
    readonly property int progressGap: 4
    readonly property int circularProgressSize: 48

    // Expressive emblem (a shaped container for an icon or artwork next to a title): 56 like a large avatar
    readonly property int emblemSize: 56

    // Text fields (md-comp-outlined/filled-text-field): 56 high, 1 dp outline/indicator that grows to 2 on focus;
    // 210 is the M3 guidance minimum width. Search bar (md-comp-search-bar): 56 high, full corner
    readonly property int textFieldHeight: 56
    readonly property int textFieldFocusWidth: 2
    readonly property int textFieldMinWidth: 210
    readonly property real disabledFilledField: 0.04       // md-comp-filled-text-field disabled container opacity
    readonly property int searchBarHeight: 56

    // Lists (md-comp-list): one/two/three-line items 56/72/88, avatar 40, image 56
    readonly property int listItemOneLine: 56
    readonly property int listItemTwoLine: 72
    readonly property int listItemThreeLine: 88
    readonly property int listAvatarSize: 40
    readonly property int listImageSize: 56

    // Top app bar (md-comp-top-app-bar-small/medium/large): 64 / 112 / 152 high
    readonly property int topAppBarSmall: 64
    readonly property int topAppBarMedium: 112
    readonly property int topAppBarLarge: 152

    // Cards (md-comp-*-card): elevated cards rest at level 1
    readonly property int cardElevation: 1

    // Empty states: the emblem is larger than an avatar-sized one and springs in from this scale
    readonly property int emptyEmblemSize: 112
    readonly property real emptyEmblemEnterScale: 0.6
    readonly property real emptyEmblemEnterTurn: -30

    // Window size classes (M3 adaptive layout): compact < 600 -> modal drawer, medium 600-839 -> rail,
    // expanded >= 840 -> standard drawer
    readonly property int windowMedium: 600
    readonly property int windowExpanded: 840
    function windowClass(width: real): string {
        return width < windowMedium ? "modal" : width < windowExpanded ? "rail" : "standard";
    }

    // Navigation drawer (md-comp-navigation-drawer): the token container width is 360; Wysun uses 280, the width
    // of the approved mock-up (docs/design/qml-migration/files-adaptive-nav.html, decision D2). Items 56 high.
    readonly property int drawerWidth: 280
    readonly property int drawerItemHeight: 56
    readonly property int navUsageWidth: 48             // usage bar of a drawer destination (Wysun: disks); not an M3 token
    readonly property int modalDrawerElevation: 1
    readonly property real scrimOpacity: 0.32

    // Navigation rail (md-comp-navigation-rail): 80 wide; active indicator 56 x 32, grows from 32
    readonly property int railWidth: 80
    readonly property int railIndicatorWidth: 56
    readonly property int railIndicatorHeight: 32

    // Tabs (md-comp-primary/secondary-navigation-tab): 48 high (64 with icon and label); indicator 3 / 2
    readonly property int tabHeight: 48
    readonly property int tabHeightWithIcon: 64
    readonly property int tabIndicatorPrimary: 3
    readonly property int tabIndicatorSecondary: 2
    readonly property int tabIndicatorMinWidth: 24

    // Menus (md-comp-menu): items 48 high, container 112-280 wide, level 2; they grow in from 80 %
    readonly property int menuInset: 4                  // M3 Expressive: rows are rounded inside the panel
    readonly property int menuItemHeight: 48
    readonly property int menuMinWidth: 112
    readonly property int menuMaxWidth: 360             // past M3's 280: long labels with their shortcut must not collide
    readonly property int menuElevation: 2
    readonly property real menuEnterScale: 0.8

    // Dialogs (md-comp-dialog): 280-560 wide, 24 padding, level 3
    readonly property int dialogMinWidth: 280
    readonly property int dialogMaxWidth: 560
    readonly property int dialogPadding: 24
    readonly property int dialogElevation: 3

    // Snackbar (md-comp-snackbar): 48 high, 68 with two lines, level 3; at most 600 wide on large windows
    readonly property int snackbarHeight: 48
    readonly property int snackbarTwoLineHeight: 68
    readonly property int snackbarMaxWidth: 600
    readonly property int snackbarElevation: 3
    // M3 guidance: 4 s, 10 s for longer messages, as multiples of the extraLarge duration token (1000 ms)
    readonly property int snackbarShortFactor: 4
    readonly property int snackbarLongFactor: 10

    // Tooltips (md-comp-plain-tooltip): plain 24 high; rich ones use the medium corner
    readonly property int tooltipHeight: 24
    readonly property int richTooltipMaxWidth: 320

    // Slider (md-comp-slider): track 4, handle 20, a 40 high target; the wavy active track (M3 Expressive
    // progress) waves 3 px either side with a 40 px wavelength
    readonly property int sliderTrack: 4
    readonly property int sliderHandle: 20
    readonly property int sliderTarget: 40
    readonly property int waveAmplitude: 3
    readonly property int waveLength: 40
}

