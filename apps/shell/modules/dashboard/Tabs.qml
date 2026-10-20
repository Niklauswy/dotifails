// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Tabs.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

Item {
    id: root
    property var motion
    property alias currentIndex: bar.currentIndex
    readonly property int count: 4
    implicitHeight: bar.implicitHeight + Wysun.Appearance.spaceS
    TabBar {
        id: bar
        objectName: "dashboardTabs"
        anchors { left: parent.left; right: parent.right; top: parent.top }
        implicitHeight: Wysun.Appearance.spaceXl * 2
        spacing: 0
        background: Item {}
        Repeater {
            model: ["Inicio", "Música", "Rendimiento", "Escritorios"]
            delegate: TabButton {
                id: tab
                required property string modelData
                required property int index
                objectName: "dashboardTab" + index
                width: bar.width / root.count
                implicitHeight: bar.implicitHeight
                padding: Wysun.Appearance.spaceXs
                text: modelData
                Accessible.name: modelData
                background: Components.StyledRect { motion: root.motion; radius: Wysun.Appearance.radiusControl; color: tab.down ? Wysun.Appearance.pressed : (tab.hovered ? Wysun.Appearance.hover : "transparent"); border.width: tab.activeFocus ? Wysun.Appearance.focusWidth : 0; border.color: Wysun.Appearance.focus }
                contentItem: Components.StyledText { text: tab.text; color: tab.checked ? Wysun.Appearance.accent : Wysun.Appearance.muted; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; font.pixelSize: Wysun.Appearance.fontBody; font.weight: tab.checked ? Font.DemiBold : Font.Normal; elide: Text.ElideRight }
            }
        }
    }
    Components.StyledRect {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: Wysun.Appearance.borderWidth
        color: Wysun.Appearance.line
    }
    Components.StyledRect {
        id: indicator
        y: bar.height
        x: root.currentIndex * bar.width/root.count + Wysun.Appearance.spaceM
        width: Math.max(0, bar.width/root.count - Wysun.Appearance.spaceM*2)
        height: Wysun.Appearance.spaceXs
        radius: height/2
        color: Wysun.Appearance.accent
        motion: root.motion
        Behavior on x { Components.Anim { motion: root.motion } }
    }
}
