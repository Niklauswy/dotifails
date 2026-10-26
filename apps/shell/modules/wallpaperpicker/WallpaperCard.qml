pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Widgets
import Wysun.Config
import qs.components
import qs.modules.background
import qs.services

// One card on the orbit ring. `t` is the signed distance (in cards) from the
// selected card around the ring; angle, depth, tilt and fade all derive from it,
// so the whole ring turns by moving a single number. `intro` drops the ring in
// spinning from the distance; `outro` flings the others away, and `toss` lifts
// the chosen card and throws it into the desktop at `impact`, where the
// wallpaper transition opens.
Item {
    id: card

    required property var entry
    required property real t
    required property real step
    required property real ringRadius
    required property real cardWidth
    required property real cardHeight
    required property point centre
    required property bool selected
    required property bool current
    required property color accent
    // Cards further than this from the front fade out (rings with more wallpapers than slots).
    property real span: 99
    property real intro: 1
    property real outro: 0
    property real toss: 0
    // The bloom has taken the card's place.
    property bool bloomed
    property point impact: centre
    // Live preview only after the selection has settled, so turning never spawns decoders.
    property bool settled

    readonly property real a: Math.abs(t)
    readonly property real theta: (t * step - (1 - intro) * 200) * Math.PI / 180
    readonly property real reach: ringRadius * (selected ? 1 : 1 + 1.4 * outro)
    // The ring leans towards the viewer and is projected orthographically: cards keep
    // their size all the way round, so the ring reads as a clean tilted ellipse.
    readonly property real tilt: -14 * Math.PI / 180
    // The throw: a short lift, then a dive that spins and straightens again as the
    // card lands at `impact`, where the bloom takes over.
    readonly property real lift: Math.min(1, toss / 0.2)
    readonly property real fly: Math.max(0, (toss - 0.2) / 0.8)
    readonly property real size: (0.6 + 0.4 * intro) * (selected ? (1 + 0.08 * lift) * (1 - 0.5 * fly) : 1)
    readonly property real spin: selected ? 24 * Math.sin(Math.PI * fly) * Math.PI / 180 : 0
    readonly property real drop: selected ? -lift * (1 - fly) * height * 0.08 + fly * (impact.y - centre.y + Math.sin(tilt) * reach) : 0
    readonly property string thumb: WallpaperLibrary.thumbFor(entry.path)

    signal clicked

    width: cardWidth
    height: cardHeight
    x: centre.x - width / 2
    // The intro drops the ring in from above.
    y: centre.y - height / 2 - (1 - intro) * height * 0.6
    z: Math.cos(theta) * 100
    opacity: Math.max(0, Math.min(1, span + 0.5 - a)) * Math.min(1, intro * 1.5) * (selected ? (bloomed ? 0 : 1) : 1 - outro)
    visible: opacity > 0.01

    // Turn about the ring's vertical axis, lean the ring by `tilt` and drop z; the
    // throw adds a spin in the screen plane. Offsets are taken from the card's centre,
    // which sits on the ring's centre.
    transform: Matrix4x4 {
        readonly property real c: Math.cos(card.theta)
        readonly property real s: Math.sin(card.theta)
        readonly property real cp: Math.cos(card.tilt)
        readonly property real sp: Math.sin(card.tilt)
        readonly property real cr: Math.cos(card.spin)
        readonly property real sr: Math.sin(card.spin)
        readonly property real k: card.size
        // Linear part: spin * size * (lean * turn), projected onto the screen.
        readonly property real l11: k * (cr * c - sr * sp * s)
        readonly property real l12: -k * sr * cp
        readonly property real l21: k * (sr * c + cr * sp * s)
        readonly property real l22: k * cr * cp
        readonly property real ox: s * card.reach
        readonly property real oy: -sp * c * card.reach + card.drop
        readonly property real hw: card.width / 2
        readonly property real hh: card.height / 2

        matrix: Qt.matrix4x4(l11, l12, 0, hw - l11 * hw - l12 * hh + ox,
                             l21, l22, 0, hh - l21 * hw - l22 * hh + oy,
                             0, 0, 1, 0,
                             0, 0, 0, 1)
    }

    Component.onCompleted: {
        if (!thumb)
            WallpaperLibrary.request(entry.path);
    }

    // Halo in the selection's accent.
    RectangularShadow {
        anchors.fill: face
        radius: face.radius
        color: card.accent
        blur: Tokens.padding.extraExtraLarge
        spread: -Tokens.padding.small
        opacity: card.selected ? 0.75 : 0

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }

    ClippingRectangle {
        id: face

        anchors.fill: parent
        radius: Tokens.rounding.extraLarge
        color: Colours.palette.m3surfaceContainerHigh
        border.width: card.selected ? 2 : 1
        border.color: card.selected ? card.accent : Qt.alpha(Colours.palette.m3onSurface, 0.18)

        Behavior on border.color {
            CAnim {}
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

        // Shade the cards as they turn away; the far side of the ring sinks into the backdrop.
        Rectangle {
            anchors.fill: parent
            color: Colours.palette.m3scrim
            opacity: Math.min(0.78, 0.2 * card.a + 0.25 * (1 - Math.cos(card.theta)))
        }

        MaterialIcon {
            visible: card.entry.animated
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: Tokens.padding.medium
            text: "animation"
            color: Colours.palette.m3onSurface
            fontStyle: Tokens.font.icon.small
        }

        MaterialIcon {
            visible: card.current
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: Tokens.padding.medium
            text: "check_circle"
            fill: 1
            color: card.accent
            fontStyle: Tokens.font.icon.medium
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: card.clicked()
    }
}
