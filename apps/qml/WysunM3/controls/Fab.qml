// M3 floating action button: the screen's primary action. small 40, regular 56, large 96 (36 icon); `extended`
// adds a label (56 high) and collapses to the icon when `expanded` turns false (e.g. while scrolling down).
// Variants pick the container role; "surface" is the low-emphasis one.
import QtQuick
import WysunM3

ButtonBase {
    id: root

    property string size: "regular"          // small | regular | large
    property string variant: "primary"       // primary | secondary | tertiary | surface
    property string icon
    property string text
    property bool extended
    property bool expanded: true
    readonly property int side: extended ? Metrics.fabRegular : size === "small" ? Metrics.fabSmall : size === "large" ? Metrics.fabLarge : Metrics.fabRegular
    readonly property int iconSize: size === "large" && !extended ? Metrics.fabLargeIconSize : Metrics.iconSize
    readonly property bool _open: extended && expanded

    implicitHeight: side
    implicitWidth: _open ? Metrics.fabExtendedLeading + glyph.width + (Theme.spacing.medium ?? 0) + label.implicitWidth + Metrics.fabExtendedTrailing : side
    width: implicitWidth
    height: implicitHeight
    clip: extended

    elevation: Metrics.fabElevation
    restRadius: size === "small" && !extended ? Theme.rounding.medium ?? 0 : size === "large" && !extended ? Theme.rounding.extraLarge ?? 0 : Theme.rounding.large ?? 0
    pressedRadius: size === "small" && !extended ? Theme.rounding.small ?? 0 : Theme.rounding.medium ?? 0
    containerColor: {
        switch (variant) {
        case "secondary":
            return Theme.m3secondaryContainer;
        case "tertiary":
            return Theme.m3tertiaryContainer;
        case "surface":
            return Theme.m3surfaceContainerHigh;
        }
        return Theme.m3primaryContainer;
    }
    contentRestColor: {
        switch (variant) {
        case "secondary":
            return Theme.m3onSecondaryContainer;
        case "tertiary":
            return Theme.m3onTertiaryContainer;
        case "surface":
            return Theme.m3primary;
        }
        return Theme.m3onPrimaryContainer;
    }

    SpringBehavior on implicitWidth {
        kind: "fastSpatial"
    }

    Icon {
        id: glyph

        x: root._open ? Metrics.fabExtendedLeading : (root.side - width) / 2
        anchors.verticalCenter: parent.verticalCenter
        name: root.icon
        size: root.iconSize
        color: root.contentColor

        SpringBehavior on x {
            kind: "fastSpatial"
        }
    }

    Label {
        id: label

        x: glyph.x + glyph.width + (Theme.spacing.medium ?? 0)
        anchors.verticalCenter: parent.verticalCenter
        visible: root.extended
        opacity: root._open ? 1 : 0
        role: "label.large"
        text: root.text
        color: root.contentColor

        SpringBehavior on opacity {
            kind: "fastEffects"
        }
    }
}
