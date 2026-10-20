// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Origen: components/controls/SearchBar.qml and modules/launcher/Content.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.

import QtQuick
import QtQuick.Controls
import "../../" as Wysun
import "../../components" as Components
TextField {
    id: root
    property var motion
    signal move(int delta)
    signal dismiss()
    implicitHeight: Wysun.Appearance.spaceXl * 2 + Wysun.Appearance.spaceS
    leftPadding: Wysun.Appearance.spaceL
    rightPadding: clearButton.width + Wysun.Appearance.spaceM
    color: Wysun.Appearance.textStrong
    placeholderTextColor: Wysun.Appearance.muted
    selectionColor: Wysun.Appearance.selection
    selectedTextColor: Wysun.Appearance.selectionText
    font.family: Wysun.Appearance.fontFamily
    font.pixelSize: Wysun.Appearance.fontBody
    placeholderText: "Buscar · > acciones · @ filtros"
    Accessible.name: "Buscar en Wysun"
    selectByMouse: true
    background: Components.StyledRect {
        radius: Wysun.Appearance.radiusL
        color: Wysun.Appearance.well
        border.width: root.activeFocus ? Wysun.Appearance.focusWidth : Wysun.Appearance.borderWidth
        border.color: root.activeFocus ? Wysun.Appearance.focus : Wysun.Appearance.line
    }
    Components.ActionButton {
        id: clearButton
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.rightMargin: Wysun.Appearance.spaceXs
        implicitWidth: Wysun.Appearance.spaceXl * 2
        implicitHeight: parent.height - Wysun.Appearance.spaceS
        motion: root.motion
        glyph: "close"
        label: "Borrar búsqueda"
        compact: true
        visible: root.text.length > 0
        onClicked: { root.clear(); root.forceActiveFocus(); }
    }
    Keys.onPressed: event => {
        var control = event.modifiers & Qt.ControlModifier;
        if (event.key === Qt.Key_Escape) { root.dismiss(); event.accepted = true; }
        else if (event.key === Qt.Key_Down || event.key === Qt.Key_Tab && !(event.modifiers & Qt.ShiftModifier) || control && (event.key === Qt.Key_J || event.key === Qt.Key_N)) { root.move(1); event.accepted = true; }
        else if (event.key === Qt.Key_Up || event.key === Qt.Key_Backtab || event.key === Qt.Key_Tab && event.modifiers & Qt.ShiftModifier || control && (event.key === Qt.Key_K || event.key === Qt.Key_P)) { root.move(-1); event.accepted = true; }
    }
}
