// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/dash/Resources.qml; modules/dashboard/performance/ (anillos con QtQuick.Shapes, sin plugin), commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "../../../" as Wysun
import "../../../components" as Components
import "../Logic.js" as Logic

// Circular gauge drawn with QtQuick.Shapes (the upstream CircularProgress comes
// from the Caelestia C++ plugin, which Wysun does not ship). A missing sample
// draws only the track and a dash: it is never shown as 0 %.
Item {
    id: root
    property var value: null
    property var motion
    property string label: ""
    property real thickness: Wysun.Appearance.spaceS
    property bool showValue: true
    readonly property var validValue: Logic.percentage(value)
    readonly property string level: Logic.usageLevel(value)
    // Semantic state colours come from the theme; the primary role is the default.
    readonly property color tone: level === "critical" ? Wysun.Appearance.danger
        : (level === "warning" ? Wysun.Appearance.warning : Wysun.Appearance.accent)
    property real displayedValue: validValue ?? 0

    implicitWidth: Wysun.Appearance.spaceXl * 4
    implicitHeight: implicitWidth
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label + ": " + Logic.percentText(value)

    Behavior on displayedValue { Components.Anim { motion: root.motion } }

    ArcPath {
        anchors.fill: parent
        sweep: 270
        stroke: Wysun.Appearance.line
        thickness: root.thickness
    }
    ArcPath {
        anchors.fill: parent
        visible: root.validValue !== null
        sweep: Logic.arcSweep(root.displayedValue)
        stroke: root.tone
        thickness: root.thickness
    }
    Components.StyledText {
        anchors.centerIn: parent
        width: parent.width - root.thickness * 3
        visible: root.showValue
        text: root.validValue === null ? "—" : Math.round(root.displayedValue) + "%"
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: Math.max(Wysun.Appearance.fontSmall, Math.min(Wysun.Appearance.fontTitle, root.width / 4))
        font.weight: Font.DemiBold
        color: root.validValue === null ? Wysun.Appearance.muted : root.tone
        motion: root.motion
    }
}
