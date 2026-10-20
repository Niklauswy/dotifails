// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Dash.qml; dash/DateTime.qml; dash/Calendar.qml; dash/Media.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "dash" as DashCards
import "Logic.js" as Logic

// "Inicio": clock, calendar, current track, resources and shortcuts. The wide
// layout is two columns; a narrow output falls back to one.
GridLayout {
    id: root
    property var metrics: null
    property var media: null
    property var controller: null
    property var motion
    property string monitorName: ""
    property date now: new Date()
    readonly property bool narrow: width < Wysun.Appearance.spaceXl * 24
    columns: narrow ? 1 : 2
    rowSpacing: Wysun.Appearance.spaceM
    columnSpacing: Wysun.Appearance.spaceM

    Timer {
        interval: 30000
        running: root.visible
        repeat: true
        onTriggered: root.now = new Date()
    }

    DashCards.DateTime {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 1
        now: root.now
        monitorName: root.monitorName
        motion: root.motion
    }
    DashCards.Calendar {
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        today: root.now
        motion: root.motion
    }
    DashCards.Media {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 1
        media: root.media
        controller: root.controller
        motion: root.motion
    }
    DashCards.Resources {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 1
        metrics: root.metrics
        motion: root.motion
    }
    RowLayout {
        Layout.columnSpan: root.columns
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceS
        Components.ActionButton {
            Layout.fillWidth: true; implicitWidth: 0
            glyph: "folder"; label: "Archivos"; motion: root.motion
            enabled: !!root.controller
            onClicked: root.controller.launch("files")
        }
        Components.ActionButton {
            Layout.fillWidth: true; implicitWidth: 0
            glyph: "library_music"; label: "Música"; motion: root.motion
            enabled: !!root.controller
            onClicked: root.controller.launch("music")
        }
        Components.ActionButton {
            Layout.fillWidth: true; implicitWidth: 0
            glyph: "settings"; label: "Ajustes"; motion: root.motion
            enabled: !!root.controller
            onClicked: root.controller.launch("settings")
        }
    }
}
