// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Calendar.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../../" as Wysun
import "../../../components" as Components
import "../" as Dashboard
import "../Logic.js" as Logic

// Month grid with Monday as the first day. Navigation is local to the card and
// returns to the current month when the surface reopens.
Dashboard.Card {
    id: root
    property date today: new Date()
    property var motion
    property int year: today.getFullYear()
    property int month: today.getMonth()
    readonly property var weeks: Logic.monthGrid(year, month, today)
    implicitHeight: layout.implicitHeight + padding * 2

    function shift(delta) {
        var next = Logic.shiftMonth(year, month, delta);
        year = next.year;
        month = next.month;
    }
    function reset() { year = today.getFullYear(); month = today.getMonth(); }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: root.padding
        spacing: Wysun.Appearance.spaceXs

        RowLayout {
            Layout.fillWidth: true
            Dashboard.IconButton {
                glyph: "chevron_left"; label: "Mes anterior"; motion: root.motion
                implicitWidth: Wysun.Appearance.spaceXl * 1.5
                onClicked: root.shift(-1)
            }
            Components.StyledText {
                Layout.fillWidth: true
                text: Logic.monthTitle(root.year, root.month)
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: Wysun.Appearance.fontBody
                font.weight: Font.Medium
                Accessible.role: Accessible.Heading
                TapHandler { onDoubleTapped: root.reset() }
            }
            Dashboard.IconButton {
                glyph: "chevron_right"; label: "Mes siguiente"; motion: root.motion
                implicitWidth: Wysun.Appearance.spaceXl * 1.5
                onClicked: root.shift(1)
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 7
            rowSpacing: 0
            columnSpacing: 0
            Repeater {
                model: Logic.WEEKDAY_HEADERS
                delegate: Components.StyledText {
                    required property string modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    text: modelData
                    horizontalAlignment: Text.AlignHCenter
                    color: Wysun.Appearance.muted
                    font.pixelSize: Wysun.Appearance.fontSmall
                }
            }
            Repeater {
                model: root.weeks.reduce(function(all, row) { return all.concat(row); }, [])
                delegate: Item {
                    id: cell
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    implicitHeight: Wysun.Appearance.spaceXl + Wysun.Appearance.spaceXs
                    Accessible.role: Accessible.StaticText
                    Accessible.name: modelData.day + (modelData.today ? ", hoy" : "")
                    Rectangle {
                        anchors.centerIn: parent
                        width: Math.min(parent.width, parent.height)
                        height: width
                        radius: width / 2
                        visible: cell.modelData.today
                        color: Wysun.Appearance.accent
                    }
                    Components.StyledText {
                        anchors.centerIn: parent
                        text: cell.modelData.day
                        font.pixelSize: Wysun.Appearance.fontSmall
                        font.weight: cell.modelData.today ? Font.DemiBold : Font.Normal
                        color: cell.modelData.today ? Wysun.Appearance.onAccent
                            : (cell.modelData.inMonth ? Wysun.Appearance.text : Wysun.Appearance.disabled)
                    }
                }
            }
        }
    }
}
