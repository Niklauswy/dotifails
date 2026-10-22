pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Widgets
import Wysun.Config
import qs.components
import qs.modules.background
import qs.services

// One carousel card. `t` is the signed distance (in cards) from the selected card;
// position, scale, tilt and fade are all derived from it so the whole strip
// animates by moving a single number.
ClippingRectangle {
    id: card

    required property var entry
    required property real t
    required property real cardWidth
    required property real cardHeight
    required property real centerX
    required property bool selected
    required property bool current
    // Live preview only after the selection has settled, so scrolling never spawns decoders.
    property bool settled

    readonly property real a: Math.abs(t)
    readonly property real sign: t < 0 ? -1 : 1
    readonly property real spread: 0.52 * cardWidth
    readonly property real falloff: 0.72
    readonly property real near: Math.min(a, 1)
    readonly property string thumb: WallpaperLibrary.thumbFor(entry.path)

    signal clicked

    width: cardWidth
    height: cardHeight
    // Geometric series: neighbours overlap progressively and pile up towards the edges.
    x: centerX - width / 2 + sign * spread * (1 - Math.pow(falloff, a)) / (1 - falloff)
    y: 0
    z: -a
    scale: 1 - 0.2 * near - 0.04 * Math.min(Math.max(a - 1, 0), 3)
    opacity: a > 4 ? Math.max(0, 1 - (a - 4) / 4) : 1
    visible: opacity > 0.01 && Math.abs(x + width / 2 - centerX) < centerX + width
    radius: Tokens.rounding.large
    color: Colours.palette.m3surfaceContainerHigh
    border.width: 1 + (1 - near)
    border.color: Qt.alpha(Colours.palette.m3onSurface, 0.25 + 0.65 * (1 - near))

    transform: Rotation {
        origin.x: card.width / 2
        origin.y: card.height / 2
        axis { x: 0; y: 1; z: 0 }
        angle: -card.sign * 60 * card.near
    }

    Component.onCompleted: {
        if (!thumb)
            WallpaperLibrary.request(entry.path);
    }

    Image {
        anchors.fill: parent
        source: card.thumb ? `file://${card.thumb}` : ""
        asynchronous: true
        cache: true
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: 480
        opacity: status === Image.Ready ? 1 : 0

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }

    MaterialIcon {
        anchors.centerIn: parent
        visible: !card.thumb
        text: card.entry.animated ? "movie" : "image"
        color: Colours.palette.m3onSurfaceVariant
        fontStyle: Tokens.font.icon.large
    }

    Loader {
        anchors.fill: parent
        active: card.selected && card.entry.animated && card.settled
        sourceComponent: WallpaperVisual {
            source: card.entry.path
            playing: true
            animate: true
        }
    }

    // Darken cards the further they sit from the selection.
    Rectangle {
        anchors.fill: parent
        color: Colours.palette.m3scrim
        opacity: Math.min(0.55, 0.14 * card.a)
    }

    Rectangle {
        visible: card.entry.animated
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: Tokens.padding.small
        implicitHeight: badgeRow.implicitHeight + Tokens.padding.small
        implicitWidth: badgeRow.implicitWidth + Tokens.padding.small * 2
        radius: Tokens.rounding.full
        color: Colours.palette.m3secondaryContainer

        Row {
            id: badgeRow

            anchors.centerIn: parent
            spacing: Tokens.spacing.extraSmall

            MaterialIcon {
                anchors.verticalCenter: parent.verticalCenter
                text: "animation"
                color: Colours.palette.m3onSecondaryContainer
                fontStyle: Tokens.font.icon.small
            }

            StyledText {
                visible: card.selected
                anchors.verticalCenter: parent.verticalCenter
                text: "Animated"
                color: Colours.palette.m3onSecondaryContainer
                font: Tokens.font.label.small
            }
        }
    }

    MaterialIcon {
        visible: card.current
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Tokens.padding.small
        text: "check_circle"
        fill: 1
        color: Colours.palette.m3primary
        fontStyle: Tokens.font.icon.medium
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: card.clicked()
    }
}
