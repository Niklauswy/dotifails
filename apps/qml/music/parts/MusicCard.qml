// A card of the music library: artwork (an album/playlist cover, a 2×2 mosaic, or an artist in a cookie), title
// and subtitle; a play button rises over the artwork on hover or focus. Enter/Space open it, Ctrl+Enter plays.
import QtQuick
import WysunM3

FocusScope {
    id: root

    property string title
    property string subtitle
    property var covers: []
    property bool round
    property bool playing
    property string placeholderIcon: round ? "person" : "album"
    property string shape: round ? "cookie" : "squircle"
    property string initials
    property bool selected
    readonly property bool hot: area.containsMouse || activeFocus

    // ≥ 0: the card rises into place after the ones before it (a staggered entrance); -1: it is just there.
    property int entranceIndex: -1

    signal opened
    signal playRequested
    signal contextRequested(real x, real y)

    transform: Translate {
        id: lift
    }

    Component.onCompleted: {
        if (entranceIndex < 0 || Motion.reduced)
            return;
        opacity = 0;
        lift.y = Theme.spacing.extraLarge ?? 0;
        entrance.start();
    }

    SequentialAnimation {
        id: entrance

        PauseAnimation {
            duration: Math.min(root.entranceIndex, 10) * Motion.ms("fastEffects") / 3
        }
        ParallelAnimation {
            Anim {
                target: root
                property: "opacity"
                to: 1
                kind: "defaultEffects"
            }
            Anim {
                target: lift
                property: "y"
                to: 0
                kind: "defaultSpatial"
            }
        }
    }

    implicitWidth: MusicMetrics.cardWidth
    implicitHeight: art.height + (Theme.spacing.small ?? 0) + texts.implicitHeight
    activeFocusOnTab: true

    Keys.onPressed: event => {
        if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter)
            return;
        event.accepted = true;
        if (event.modifiers & Qt.ControlModifier)
            root.playRequested();
        else
            root.opened();
    }

    Cover {
        id: art

        width: root.width
        height: width
        sources: root.covers
        shape: root.shape
        placeholderIcon: root.placeholderIcon
        initials: root.initials
        fill: root.round ? Theme.m3tertiaryContainer : Theme.m3surfaceContainerHighest
        placeholderColor: root.round ? Theme.m3onTertiaryContainer : Theme.m3onSurfaceVariant
        scale: area.pressed ? 0.96 : 1

        SpringBehavior on scale {
            kind: "fastSpatial"
        }
    }

    Rectangle {
        anchors.fill: art
        radius: root.round ? width / 2 : Theme.rounding.large ?? 0
        color: "transparent"
        border.width: root.selected ? Metrics.textFieldFocusWidth : 0
        border.color: Theme.m3primary
    }

    Column {
        id: texts

        y: art.height + (Theme.spacing.small ?? 0)
        width: root.width

        Label {
            width: parent.width
            role: "title.small"
            text: root.title
            elide: Text.ElideRight
            horizontalAlignment: root.round ? Text.AlignHCenter : Text.AlignLeft
        }
        Label {
            width: parent.width
            role: "body.small"
            text: root.subtitle
            color: Theme.m3onSurfaceVariant
            elide: Text.ElideRight
            horizontalAlignment: root.round ? Text.AlignHCenter : Text.AlignLeft
        }
    }

    MouseArea {
        id: area

        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) {
                const p = mapToItem(null, mouse.x, mouse.y);
                root.contextRequested(p.x, p.y);
            } else {
                root.opened();
            }
        }
    }

    Fab {
        objectName: "cardPlay"
        size: "small"
        variant: "primary"
        icon: root.playing ? "pause" : "play_arrow"
        x: art.width - width - (Theme.spacing.small ?? 0)
        y: art.height - height - (Theme.spacing.small ?? 0) + (root.hot || root.playing ? 0 : Theme.spacing.small ?? 0)
        opacity: root.hot || root.playing ? 1 : 0
        visible: opacity > 0
        onClicked: root.playRequested()

        SpringBehavior on y {
            kind: "fastSpatial"
        }
        SpringBehavior on opacity {
            kind: "fastEffects"
        }
    }

    FocusRing {
        target: art
        visible: root.activeFocus
    }
}
