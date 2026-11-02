import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services

// One action row: icon, text, optional trailing detail and chevron or external mark.
Item {
    id: root

    property string icon
    property string text
    property string detail
    property color dot: "transparent"
    property string trailing  // material symbol after the detail, e.g. "chevron_right" or "open_in_new"
    property bool enabled: true

    signal clicked

    Layout.fillWidth: true
    implicitHeight: row.implicitHeight + Tokens.padding.small * 2
    opacity: enabled ? 1 : 0.5

    StateLayer {
        radius: Tokens.rounding.medium
        disabled: !root.enabled
        color: Colours.palette.m3onSurface
        onClicked: root.clicked()
    }

    RowLayout {
        id: row

        anchors.fill: parent
        anchors.leftMargin: Tokens.padding.small
        anchors.rightMargin: Tokens.padding.small
        spacing: Tokens.spacing.medium

        MaterialIcon {
            text: root.icon
            color: Colours.palette.m3onSurfaceVariant
            fontStyle: Tokens.font.icon.medium
        }

        StyledText {
            Layout.fillWidth: true
            text: root.text
            font: Tokens.font.label.large
            elide: Text.ElideRight
        }

        Rectangle {
            visible: root.dot.a > 0
            implicitWidth: Tokens.spacing.small
            implicitHeight: implicitWidth
            radius: width / 2
            color: root.dot
        }

        StyledText {
            visible: !!root.detail
            Layout.maximumWidth: root.width / 2
            text: root.detail
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
            elide: Text.ElideMiddle
        }

        MaterialIcon {
            visible: !!root.trailing
            text: root.trailing
            color: Colours.palette.m3onSurfaceVariant
            fontStyle: Tokens.font.icon.small
        }
    }
}
