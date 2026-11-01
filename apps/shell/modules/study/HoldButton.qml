import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Hold to confirm: a primary pill grows from the left inside the button while it is held, the label turning
// to on-primary as the fill passes under it. Let go and it drains back quickly. Completes after `holdTime`.
StyledRect {
    id: root

    property alias text: label.text
    property string icon: "logout"
    property int holdTime: Tokens.anim.durations.extraLarge * 1.5
    property real progress

    signal completed

    function press(): void {
        fill.stop();
        fill.to = 1;
        fill.easing.type = Easing.InOutQuad;
        fill.duration = root.holdTime * (1 - root.progress);
        fill.start();
    }

    function release(): void {
        if (root.progress >= 1)
            return;
        fill.stop();
        fill.to = 0;
        fill.easing.type = Easing.OutCubic;
        fill.duration = Tokens.anim.durations.normal * root.progress;
        fill.start();
    }

    implicitWidth: content.implicitWidth + Tokens.padding.large * 2
    implicitHeight: Tokens.padding.extraLarge + Tokens.padding.medium
    radius: height / 2
    color: Colours.palette.m3secondaryContainer
    scale: mouse.pressed ? 0.97 : 1

    Behavior on scale {
        Anim {
            type: Anim.FastSpatial
        }
    }

    NumberAnimation {
        id: fill

        target: root
        property: "progress"
        onFinished: if (root.progress >= 1) root.completed()
    }

    component Content: Row {
        property color ink

        spacing: Tokens.spacing.small

        MaterialIcon {
            anchors.verticalCenter: parent.verticalCenter
            text: root.icon
            color: parent.ink
            fill: 1
            fontStyle: Tokens.font.icon.small
        }

        StyledText {
            anchors.verticalCenter: parent.verticalCenter
            text: label.text
            color: parent.ink
            font: Tokens.font.label.large
        }
    }

    Content {
        id: content

        anchors.centerIn: parent
        ink: Colours.palette.m3onSecondaryContainer
    }

    // The fill: a pill of its own, so its leading edge stays round while it grows.
    Item {
        width: root.progress > 0 ? Math.max(root.height, root.width * root.progress) : 0
        height: root.height
        clip: true

        Rectangle {
            width: parent.width
            height: parent.height
            radius: height / 2
            color: Colours.palette.m3primary
        }

        Content {
            x: content.x
            y: content.y
            ink: Colours.palette.m3onPrimary
        }
    }

    // Holds the text for both layers.
    StyledText {
        id: label

        visible: false
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onPressed: root.press()
        onReleased: root.release()
    }
}
