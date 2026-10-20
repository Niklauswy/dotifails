// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: modules/utilities/cards/Toggles.qml
// Commit: 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

Button {
    id: root
    property string label: ""
    property string glyph: ""
    property bool selected: false
    property var motion
    text: label
    implicitHeight: Wysun.Appearance.fontBody + Wysun.Appearance.spaceL * 2
    implicitWidth: contentItem.implicitWidth + Wysun.Appearance.spaceL * 2
    padding: Wysun.Appearance.spaceM
    activeFocusOnTab: true
    Accessible.name: label
    Accessible.role: Accessible.Button
    background: Components.StyledRect {
        motion: root.motion
        radius: Wysun.Appearance.radiusControl
        color: !root.enabled ? Wysun.Appearance.well : root.down ? Wysun.Appearance.pressed : root.selected ? Wysun.Appearance.selection : root.hovered ? Wysun.Appearance.hover : Wysun.Appearance.surfaceRaised
        border.width: root.activeFocus ? Wysun.Appearance.focusWidth : Wysun.Appearance.borderWidth
        border.color: root.activeFocus ? Wysun.Appearance.focus : Wysun.Appearance.line
    }
    contentItem: RowLayout {
        spacing: Wysun.Appearance.spaceS
        Components.MaterialIcon {
            visible: root.glyph !== ""
            name: root.glyph
            size: Wysun.Appearance.fontHeading + Wysun.Appearance.spaceXs
            color: !root.enabled ? Wysun.Appearance.disabled : root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.text
        }
        Components.StyledText {
            Layout.fillWidth: true
            text: root.label
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            color: !root.enabled ? Wysun.Appearance.disabled : root.selected ? Wysun.Appearance.selectionText : Wysun.Appearance.text
            font.pixelSize: Wysun.Appearance.fontBody
        }
    }
}
