import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Fills left to right while held; let go and it empties. Completes after `holdTime`.
StyledRect {
    id: root

    property alias text: label.text
    property int holdTime: Tokens.anim.durations.extraLarge * 2.5
    property real progress

    signal completed

    implicitWidth: label.implicitWidth + Tokens.padding.large * 2
    implicitHeight: Tokens.padding.extraLarge + Tokens.padding.medium
    radius: mouse.pressed ? Tokens.rounding.medium : height / 2
    color: Colours.palette.m3surfaceContainerHighest
    clip: true

    Behavior on radius {
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

    Rectangle {
        width: parent.width * root.progress
        height: parent.height
        color: Colours.palette.m3primaryContainer
    }

    StyledText {
        id: label

        anchors.centerIn: parent
        color: Colours.palette.m3onSurface
        font: Tokens.font.label.large
    }

    MouseArea {
        id: mouse

        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onPressed: {
            fill.stop();
            fill.to = 1;
            fill.duration = root.holdTime * (1 - root.progress);
            fill.start();
        }
        onReleased: {
            if (root.progress >= 1)
                return;
            fill.stop();
            fill.to = 0;
            fill.duration = root.holdTime * root.progress / 3;
            fill.start();
        }
    }
}
