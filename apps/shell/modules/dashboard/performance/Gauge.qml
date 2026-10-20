// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Resources.qml; modules/dashboard/performance/MemoryCard.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Shapes
import "../../../" as Wysun
import "../../../components" as Components
import "../Logic.js" as Logic

Item {
    id: root
    property var value: null
    property var motion
    property color accent: Wysun.Appearance.accent
    property string label: ""
    readonly property var validValue: Logic.percentage(value)
    property real displayedValue: validValue ?? 0
    implicitWidth: Wysun.Appearance.spaceXl * 5
    implicitHeight: implicitWidth
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label + ": " + Logic.percentText(value)
    Behavior on displayedValue { Components.Anim { motion: root.motion } }
    Shape {
        anchors.fill: parent
        antialiasing: true
        ShapePath {
            fillColor: "transparent"
            strokeColor: Wysun.Appearance.line
            strokeWidth: Wysun.Appearance.spaceXs
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.width/2; centerY: root.height/2; radiusX: (root.width-Wysun.Appearance.spaceS)/2; radiusY: (root.height-Wysun.Appearance.spaceS)/2; startAngle: 135; sweepAngle: 270 }
        }
        ShapePath {
            fillColor: "transparent"
            strokeColor: root.validValue === null ? Wysun.Appearance.line : root.accent
            strokeWidth: Wysun.Appearance.spaceXs
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: root.width/2; centerY: root.height/2; radiusX: (root.width-Wysun.Appearance.spaceS)/2; radiusY: (root.height-Wysun.Appearance.spaceS)/2; startAngle: 135; sweepAngle: 270 * root.displayedValue / 100 }
        }
    }
    Components.StyledText {
        anchors.centerIn: parent
        width: parent.width - Wysun.Appearance.spaceL
        text: root.validValue === null ? "—" : Math.round(root.displayedValue) + "%"
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: Wysun.Appearance.fontTitle
        color: root.accent
    }
}
