import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../Logic.js" as Logic
import "../../" as Wysun
import "../../components" as Components

ColumnLayout {
    id: root
    required property var workspaces
    required property var motion

    spacing: Wysun.Appearance.spaceXs
    Repeater {
        model: root.workspaces
        delegate: Button {
            required property var modelData
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 42
            Layout.preferredHeight: 32
            padding: 0
            text: Logic.workspaceLabel(modelData)
            Accessible.name: "Escritorio " + text
            Accessible.role: Accessible.Button
            onClicked: modelData.activate()

            background: Components.StyledRect {
                motion: root.motion
                radius: Wysun.Appearance.radiusControl
                color: modelData.active ? Wysun.Appearance.accent : (parent.hovered ? Wysun.Appearance.hover : "transparent")
            }
            contentItem: Components.StyledText {
                motion: root.motion
                text: parent.text
                color: modelData.active ? Wysun.Appearance.onAccent : Wysun.Appearance.text
                font.pixelSize: Wysun.Appearance.fontSmall
                font.weight: modelData.active ? Font.DemiBold : Font.Normal
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
