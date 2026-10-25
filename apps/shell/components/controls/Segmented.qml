pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Pill segmented control: [{ value, text }].
StyledRect {
    id: root

    property var options: []
    property string current

    signal selected(value: string)

    implicitWidth: segments.implicitWidth + Tokens.padding.extraSmall * 2
    implicitHeight: segments.implicitHeight + Tokens.padding.extraSmall * 2
    radius: Tokens.rounding.full
    color: Colours.tPalette.m3surfaceContainerHigh

    Row {
        id: segments

        anchors.centerIn: parent

        Repeater {
            model: root.options

            StyledRect {
                id: segment

                required property var modelData
                readonly property bool active: root.current === modelData.value

                implicitWidth: label.implicitWidth + Tokens.padding.medium * 2
                implicitHeight: label.implicitHeight + Tokens.padding.extraSmall * 2
                radius: Tokens.rounding.full
                color: active ? Colours.palette.m3primary : "transparent"

                StateLayer {
                    radius: Tokens.rounding.full
                    color: segment.active ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
                    onClicked: root.selected(segment.modelData.value)
                }

                StyledText {
                    id: label

                    anchors.centerIn: parent
                    text: segment.modelData.text
                    font: Tokens.font.label.medium
                    color: segment.active ? Colours.palette.m3onPrimary : Colours.palette.m3onSurfaceVariant
                }
            }
        }
    }
}
