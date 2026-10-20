// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Tabs.qml; modules/dashboard/media/Details.qml (controles circulares), commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Controls
import "../../" as Wysun
import "../../components" as Components

// Round icon control used by the media transport and the calendar. `prominent`
// paints the primary role (play / pause) with its on-colour glyph.
Button {
    id: root
    property string glyph: "circle"
    property string label: ""
    property bool prominent: false
    property int iconSize: Wysun.Appearance.fontHeading + Wysun.Appearance.spaceXs
    property var motion

    implicitWidth: iconSize + Wysun.Appearance.spaceL * 2
    implicitHeight: implicitWidth
    padding: 0
    focusPolicy: Qt.TabFocus
    Accessible.name: label
    Accessible.role: Accessible.Button
    opacity: enabled ? 1 : 0.45

    background: Components.StyledRect {
        motion: root.motion
        radius: root.prominent ? Wysun.Appearance.radiusL : width / 2
        color: root.prominent
            ? (root.down ? Wysun.Appearance.accentPressed : (root.hovered ? Wysun.Appearance.accentHover : Wysun.Appearance.accent))
            : (root.down ? Wysun.Appearance.pressed : (root.hovered ? Wysun.Appearance.hover : "transparent"))
        border.width: root.activeFocus ? Wysun.Appearance.focusWidth * 2 : 0
        border.color: Wysun.Appearance.focus
    }
    contentItem: Components.MaterialIcon {
        name: root.glyph
        size: root.iconSize
        color: root.prominent ? Wysun.Appearance.onAccent : Wysun.Appearance.text
    }
}
