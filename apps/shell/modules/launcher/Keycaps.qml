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

            width: Math.max(height, label.implicitWidth + Tokens.padding.small * 1.5)
            height: label.implicitHeight + Tokens.padding.extraSmall * 1.5
            radius: Tokens.rounding.extraSmall
            color: Colours.tPalette.m3surfaceContainerHighest

            StyledText {
                id: label

                anchors.centerIn: parent
                text: cap.modelData
                font: Tokens.font.label.small
                color: root.textColor
            }
        }
    }
}
