// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Tabs.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components

// Equal-width tabs with an icon and a label. The upstream control is a TabBar;
// Wysun keeps the four upstream slots (Weather is replaced by Escritorios) and
// lays plain buttons in a Row so the indicator follows the geometry directly.
Item {
    id: root
    property var motion
    property int currentIndex: 0
    readonly property int count: 4
    readonly property var labels: ["Inicio", "Música", "Rendimiento", "Escritorios"]
    readonly property var glyphs: ["home", "music_note", "speed", "grid_view"]
    signal selected(int index)

    implicitHeight: tabRow.height + Wysun.Appearance.spaceS

    function activate(index) {
        var bounded = Math.max(0, Math.min(root.count - 1, index));
        root.currentIndex = bounded;
        root.selected(bounded);
        var button = repeater.itemAt(bounded);
        if (button) button.forceActiveFocus();
    }

    Row {
        id: tabRow
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Wysun.Appearance.spaceXl * 2
        spacing: 0

        Repeater {
            id: repeater
            model: root.labels.length
            delegate: Button {
                id: tab
                required property int index
                width: tabRow.width / root.count
                height: tabRow.height
                padding: Wysun.Appearance.spaceXs
                text: root.labels[index]
                Accessible.name: root.labels[index]
                Accessible.role: Accessible.Button
                Accessible.description: index === root.currentIndex ? "Pestaña activa" : "Pestaña"
                focusPolicy: Qt.TabFocus
                onClicked: root.activate(index)
                Keys.onLeftPressed: root.activate(index - 1)
                Keys.onRightPressed: root.activate(index + 1)
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Home) {
                        root.activate(0);
                        event.accepted = true;
                    } else if (event.key === Qt.Key_End) {
                        root.activate(root.count - 1);
                        event.accepted = true;
                    }
                }

                background: Components.StyledRect {
                    motion: root.motion
                    radius: Wysun.Appearance.radiusControl
                    color: tab.down ? Wysun.Appearance.pressed
                        : (tab.hovered ? Wysun.Appearance.hover : "transparent")
                    border.width: tab.activeFocus ? Wysun.Appearance.focusWidth : 0
                    border.color: Wysun.Appearance.focus
                }

                contentItem: Item {
                    implicitWidth: label.implicitWidth + icon.width + Wysun.Appearance.spaceS
                    Row {
                        anchors.centerIn: parent
                        spacing: Wysun.Appearance.spaceS
                        Components.MaterialIcon {
                            id: icon
                            name: root.glyphs[tab.index]
                            size: Wysun.Appearance.fontHeading
                            color: tab.index === root.currentIndex ? Wysun.Appearance.accent : Wysun.Appearance.muted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Components.StyledText {
                            id: label
                            text: tab.text
                            color: tab.index === root.currentIndex ? Wysun.Appearance.accent : Wysun.Appearance.muted
                            font.pixelSize: Wysun.Appearance.fontBody
                            font.weight: tab.index === root.currentIndex ? Font.DemiBold : Font.Normal
                            elide: Text.ElideRight
                            width: Math.min(implicitWidth, tab.width - icon.width - Wysun.Appearance.spaceL)
                            anchors.verticalCenter: parent.verticalCenter
                            motion: root.motion
                        }
                    }
                }
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
        y: tabRow.height
        x: root.currentIndex * tabRow.width / root.count + Wysun.Appearance.spaceM
        width: Math.max(0, tabRow.width / root.count - Wysun.Appearance.spaceM * 2)
        height: Wysun.Appearance.spaceXs
        radius: height / 2
        color: Wysun.Appearance.accent
        motion: root.motion
        Behavior on x { Components.Anim { motion: root.motion } }
        Behavior on width { Components.Anim { motion: root.motion } }
    }
}
