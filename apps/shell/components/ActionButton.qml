import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../" as Wysun

Button {
    id: root
    property string label: ""
    property string glyph: "circle"
    property bool compact: false
    property bool selected: false
    property var motion

    implicitWidth: compact ? 48 : 184
    implicitHeight: 44
    padding: 8
    Accessible.name: label
    Accessible.role: Accessible.Button

    background: StyledRect {
        motion: root.motion
        radius: Wysun.Appearance.radiusControl
        color: root.down ? Wysun.Appearance.pressed : (root.selected ? Wysun.Appearance.selection : (root.hovered ? Wysun.Appearance.hover : "transparent"))
        border.width: root.activeFocus ? Wysun.Appearance.focusWidth : 0
        border.color: Wysun.Appearance.focus
    }

    contentItem: RowLayout {
        spacing: 8
        MaterialIcon { name: root.glyph; size: 20; color: root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.text }
        StyledText {
            visible: !root.compact
            Layout.fillWidth: true
            text: root.label
            elide: Text.ElideRight
            color: root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.text
            font.pixelSize: Wysun.Appearance.fontSmall
            motion: root.motion
        }
    }
}
