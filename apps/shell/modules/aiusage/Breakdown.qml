pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services
import "Format.js" as Format

// A titled list of name, share bar, percentage and value; items: [{name, share, value, icon}].
ColumnLayout {
    id: breakdown

    property string title
    property var items: []

    Layout.fillWidth: true
    spacing: Tokens.spacing.small

    StyledText {
        Layout.leftMargin: Tokens.padding.small
        Layout.topMargin: Tokens.spacing.small
        text: breakdown.title
        font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
        color: Colours.palette.m3onSurfaceVariant
    }

    Repeater {
        model: breakdown.items

        RowLayout {
            id: item

            required property var modelData

            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.rightMargin: Tokens.padding.small
            spacing: Tokens.spacing.medium

            MaterialIcon {
                visible: !!item.modelData.icon
                text: item.modelData.icon
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }

            StyledText {
                Layout.fillWidth: true
                text: item.modelData.name
                font: Tokens.font.body.small
                elide: Text.ElideRight
            }

            StyledRect {
                implicitWidth: Tokens.spacing.extraExtraLarge * 2
                implicitHeight: Tokens.sizes.aiUsage.typeBarHeight
                radius: Tokens.rounding.full
                color: Qt.alpha(Colours.palette.m3onSurface, 0.09)

                StyledRect {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width * Math.max(0, Math.min(1, item.modelData.share))
                    radius: Tokens.rounding.full
                    color: Colours.palette.m3primary
                }
            }

            StyledText {
                Layout.preferredWidth: Tokens.spacing.extraLarge + Tokens.spacing.medium
                horizontalAlignment: Text.AlignRight
                text: Format.percent(item.modelData.share)
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }

            StyledText {
                Layout.preferredWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.large
                horizontalAlignment: Text.AlignRight
                text: item.modelData.value
                font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
            }
        }
    }
}
