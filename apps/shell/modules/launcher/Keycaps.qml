import QtQuick
import Wysun.Config
import qs.components
import qs.services

// A row of small key labels, e.g. Ctrl K. ``onPrimary`` tints them for a filled primary button.
Row {
    id: root

    property var keys: []
    property bool onPrimary
    property color textColor: onPrimary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurfaceVariant

    spacing: Tokens.spacing.extraSmall

    Repeater {
        model: root.keys

        Rectangle {
            id: cap

            required property string modelData

            width: Math.max(height, label.implicitWidth + Tokens.padding.small * 1.5)
            height: 22
            radius: Tokens.rounding.small
            color: root.onPrimary ? Qt.alpha(Colours.palette.m3onPrimary, 0.18) : Colours.palette.m3surfaceContainerLow

            StyledText {
                id: label

                anchors.centerIn: parent
                text: cap.modelData
                font: Tokens.font.body.builders.small.size(8.5).weight(Font.DemiBold).build()
                color: root.textColor
            }
        }
    }
}
