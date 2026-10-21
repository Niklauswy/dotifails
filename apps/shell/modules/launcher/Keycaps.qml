import QtQuick
import Wysun.Config
import qs.components
import qs.services

// A row of small key labels, e.g. Ctrl K.
Row {
    id: root

    property var keys: []
    property color textColor: Colours.palette.m3onSurfaceVariant

    spacing: Tokens.spacing.extraSmall

    Repeater {
        model: root.keys

        Rectangle {
            id: cap

            required property string modelData

            width: Math.max(height, label.implicitWidth + Tokens.padding.small)
            height: 20
            radius: Tokens.rounding.extraSmall + 1
            color: Qt.alpha(Colours.palette.m3onSurface, 0.12)

            StyledText {
                id: label

                anchors.centerIn: parent
                text: cap.modelData
                font: Tokens.font.body.builders.small.size(8.25).weight(Font.Medium).build()
                color: root.textColor
            }
        }
    }
}
