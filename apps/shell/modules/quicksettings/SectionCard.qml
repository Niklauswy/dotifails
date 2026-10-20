// Adaptado de caelestia-dots/shell/modules/utilities/Content.qml (GPL-3.0),
// modificado para Wysun. Fuente: caelestia-dots/shell, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

Components.StyledRect {
    id: root

    required property var motion
    property string title: ""
    property string subtitle: ""
    default property alias content: column.data

    implicitHeight: column.implicitHeight + Wysun.Appearance.spaceL * 2
    radius: Wysun.Appearance.radiusL
    color: Wysun.Appearance.surfaceRaised
    border.width: Wysun.Appearance.borderWidth
    border.color: Wysun.Appearance.line

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Wysun.Appearance.spaceL
        spacing: Wysun.Appearance.spaceS
        Components.StyledText {
            visible: root.title.length > 0
            Layout.fillWidth: true
            text: root.title
            color: Wysun.Appearance.textStrong
            font.pixelSize: Wysun.Appearance.fontHeading
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
            motion: root.motion
            Accessible.role: Accessible.Heading
        }
        Components.StyledText {
            visible: root.subtitle.length > 0
            Layout.fillWidth: true
            text: root.subtitle
            color: Wysun.Appearance.muted
            font.pixelSize: Wysun.Appearance.fontSmall
            wrapMode: Text.WordWrap
            motion: root.motion
        }
    }
}
