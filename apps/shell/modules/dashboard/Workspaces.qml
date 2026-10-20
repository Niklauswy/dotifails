// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/dashboard/Content.qml (cuarta pestaña sustituida: Weather -> Escritorios, modelo Hyprland de Wysun), commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import QtQuick.Layouts
import "../../" as Wysun
import "../../components" as Components
import "Logic.js" as Logic

// "Escritorios": the Hyprland workspaces of this output with their windows.
// The model is the one the rail already uses (Hyprland.workspaces); nothing is
// created, moved or closed here, only focused.
ColumnLayout {
    id: root
    property var workspaces: []
    property var windows: []
    property var controller: null
    property var motion
    spacing: Wysun.Appearance.spaceM

    RowLayout {
        Layout.fillWidth: true
        spacing: Wysun.Appearance.spaceS
        Components.MaterialIcon { name: "grid_view"; size: Wysun.Appearance.fontHeading; color: Wysun.Appearance.accent }
        Components.StyledText {
            Layout.fillWidth: true
            text: "Tus escritorios"
            font.pixelSize: Wysun.Appearance.fontHeading
            font.weight: Font.Medium
            Accessible.role: Accessible.Heading
        }
    }
    Components.StyledText {
        Layout.fillWidth: true
        visible: root.workspaces.length === 0
        text: "No hay escritorios disponibles en esta pantalla."
        wrapMode: Text.WordWrap
        font.pixelSize: Wysun.Appearance.fontBody
        color: Wysun.Appearance.muted
    }

    GridLayout {
        Layout.fillWidth: true
        columns: width < Wysun.Appearance.spaceXl * 24 ? 1 : 2
        rowSpacing: Wysun.Appearance.spaceM
        columnSpacing: Wysun.Appearance.spaceM
        Repeater {
            model: root.workspaces
            delegate: Card {
                id: desktop
                required property var modelData
                readonly property var clients: Logic.windowsOfDesktop(root.windows, modelData)
                readonly property bool current: modelData.active === true || modelData.focused === true
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                color: current ? Wysun.Appearance.selection : Wysun.Appearance.surfaceRaised
                implicitHeight: desktopLayout.implicitHeight + padding * 2
                Accessible.role: Accessible.Grouping
                Accessible.name: "Escritorio " + modelData.name + (current ? ", actual" : "")

                ColumnLayout {
                    id: desktopLayout
                    anchors.fill: parent
                    anchors.margins: desktop.padding
                    spacing: Wysun.Appearance.spaceXs
                    Components.ActionButton {
                        Layout.fillWidth: true
                        motion: root.motion
                        glyph: desktop.current ? "check_circle" : "desktop_windows"
                        selected: desktop.current
                        label: "Escritorio " + desktop.modelData.name + (desktop.current ? " · actual" : "")
                        onClicked: {
                            desktop.modelData.activate();
                            if (root.controller) root.controller.close();
                        }
                    }
                    Repeater {
                        model: desktop.clients
                        delegate: Components.ActionButton {
                            required property var modelData
                            Layout.fillWidth: true
                            glyph: "open_in_new"
                            label: Logic.windowTitle(modelData)
                            motion: root.motion
                            enabled: !!root.controller && !!modelData.wayland
                            onClicked: root.controller.activateWindow(modelData)
                        }
                    }
                    Components.StyledText {
                        visible: desktop.clients.length === 0
                        Layout.leftMargin: Wysun.Appearance.spaceS
                        text: "Sin ventanas"
                        font.pixelSize: Wysun.Appearance.fontSmall
                        color: desktop.current ? Wysun.Appearance.selectionText : Wysun.Appearance.muted
                    }
                }
            }
        }
    }
}
