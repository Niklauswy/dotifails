import QtQuick
import QtQuick.Layouts

// Reference widget: everything visual comes from Appearance, so it follows
// the style and variant live. Copy this file as the starting point of a new
// shell widget (see docs/themes.md).
Rectangle {
    id: demo
    property string title: "Tema de Wysun"
    implicitWidth: 260
    implicitHeight: 96
    radius: Appearance.radiusM
    color: Appearance.surface
    border.width: Appearance.borderWidth
    border.color: Appearance.line

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Appearance.spaceM
        spacing: Appearance.spaceS
        Text {
            text: demo.title
            color: Appearance.text
            font { family: Appearance.fontFamily; pixelSize: Appearance.fontHeading; weight: Font.DemiBold }
        }
        Text {
            text: Appearance.style + " · " + Appearance.name
            color: Appearance.muted
            font { family: Appearance.fontFamily; pixelSize: Appearance.fontSmall }
        }
        Rectangle {
            Layout.preferredWidth: 72
            Layout.preferredHeight: 6
            radius: 3
            color: Appearance.accent
        }
    }
}
