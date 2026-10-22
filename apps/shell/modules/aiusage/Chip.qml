import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Small tinted label, used for plans.
StyledRect {
    id: root

    property alias text: label.text
    property color accent: Colours.palette.m3primary

    implicitWidth: label.implicitWidth + Tokens.padding.small * 2
    implicitHeight: label.implicitHeight + Tokens.padding.extraSmall
    radius: Tokens.rounding.full
    color: Qt.alpha(accent, 0.18)

    StyledText {
        id: label

        anchors.centerIn: parent
        font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
        color: root.accent
    }
}
