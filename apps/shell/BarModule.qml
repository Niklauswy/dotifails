pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray
import Quickshell.Services.UPower
import "Logic.js" as Logic

Item {
    id: root
    required property string kind
    required property var barWindow
    required property var preferences
    required property var controller
    required property var clock
    required property var resources
    readonly property var monitor: barWindow.monitor
    readonly property var sink: kind === "volume" ? Pipewire.defaultAudioSink : null
    readonly property bool trayVisible: kind === "tray" && barWindow.screen !== null && Logic.trayMonitor(preferences.environment, Quickshell.screens, preferences.nativeBarData) === barWindow.screen.name
    readonly property var workspaces: monitor ? Logic.sortWorkspaces(Hyprland.workspaces.values.filter(w => w.monitor === monitor)) : []
    readonly property bool compact: barWindow.compact
    visible: (kind !== "tray" || trayVisible)
        && (kind !== "battery" || (UPower.displayDevice.ready && UPower.displayDevice.isLaptopBattery))
        && (kind !== "title" || barWindow.presentation.showTitle)
        && (kind !== "resources" || barWindow.presentation.showResources)
    implicitWidth: visible ? content.implicitWidth : 0
    implicitHeight: barWindow.implicitHeight
    PwObjectTracker { objects: root.sink ? [root.sink] : [] }
    Loader {
        id: content
        anchors.fill: parent
        sourceComponent: root.kind === "workspaces" ? workspaceComponent : (root.kind === "tray" ? trayComponent : actionComponent)
    }
    Component {
        id: actionComponent
        ShellButton {
            foreground: root.preferences.bar.foreground || Appearance.text
            accent: root.preferences.bar.accent || Appearance.accent
            glyph: root.barWindow.presentation.iconControls ? ({ network: "wifi", volume: "music", notifications: "bell" })[root.kind] || "" : ""
            implicitWidth: root.kind === "title" ? (root.compact ? 64 : 200) : (root.kind === "resources" && root.compact ? 64 : Math.max(36, implicitContentWidth + leftPadding + rightPadding))
            text: {
                if (glyph) return "";
                switch (root.kind) {
                case "orbit": return "Wysun";
                case "title": return Hyprland.activeToplevel?.monitor === root.monitor ? Hyprland.activeToplevel.title : "Escritorio";
                case "resources": return root.compact ? "Sistema" : root.resources.label;
                case "network": return "Red";
                case "volume": return root.sink?.audio ? (root.sink.audio.muted ? "Silencio" : Math.round(root.sink.audio.volume * 100) + "% ♪") : "Audio";
                case "battery": return Math.round(UPower.displayDevice.percentage * 100) + "%";
                case "date": return Qt.formatDateTime(root.clock.date, root.barWindow.presentation.dateFormat);
                case "notifications": return "Avisos";
                case "power": return "⏻";
                default: return "";
                }
            }
            description: ({ orbit: "Abrir lanzador Wysun · clic derecho: Centro de escritorio", title: "Mostrar ventanas", resources: "CPU y memoria · abrir procesos", network: "Conexiones", volume: "Abrir audio", battery: "Batería · abrir energía", date: "Abrir calendario", notifications: "Dunst: historial, acciones y concentración", power: "Energía y sesión" })[root.kind] || text
            onClicked: {
                if (root.kind === "orbit") root.controller.launch("launcher");
                else if (root.kind === "title") root.controller.toggle("windows", root.barWindow.screen.name);
                else if (root.kind === "power") root.controller.toggle("session", root.barWindow.screen.name);
                else root.controller.launch(({ resources: "processes", network: "connections", volume: "audio", battery: "power", date: "calendar", notifications: "notifications" })[root.kind]);
            }
            secondaryActionEnabled: root.kind === "orbit"
            onSecondaryClicked: root.controller.secondaryClick(root.barWindow.screen.name)
            Keys.onMenuPressed: if (root.kind === "orbit") root.controller.toggle("menu", root.barWindow.screen.name)
        }
    }
    Component {
        id: workspaceComponent
        Flickable {
            implicitWidth: Math.min(workspaceRow.implicitWidth, Math.max(60, root.barWindow.width * 0.24))
            implicitHeight: root.implicitHeight
            contentWidth: workspaceRow.implicitWidth
            contentHeight: height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Row {
                id: workspaceRow
                spacing: 2
                Repeater {
                    model: root.workspaces
                    ShellButton {
                        required property var modelData
                        height: root.implicitHeight
                        foreground: root.preferences.bar.foreground || Appearance.text
                        accent: root.preferences.bar.accent || Appearance.accent
                        text: Logic.workspaceLabel(modelData)
                        description: "Escritorio " + Logic.workspaceLabel(modelData) + (modelData.urgent ? ", requiere atención" : "")
                        selected: modelData.active
                        onClicked: modelData.activate()
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 12; height: 2
                            visible: parent.modelData.urgent
                            color: Appearance.accent
                        }
                    }
                }
            }
        }
    }
    Component {
        id: trayComponent
        Row {
            spacing: 2
            Repeater {
                model: root.trayVisible ? SystemTray.items : null
                ShellButton {
                    id: trayButton
                    required property var modelData
                    height: root.implicitHeight
                    text: ""
                    description: modelData.tooltipTitle || modelData.title || modelData.id
                    implicitWidth: 36
                    onClicked: {
                        if (modelData.onlyMenu) showMenu();
                        else modelData.activate();
                    }
                    function showMenu() {
                        var point = mapToItem(root.barWindow.contentItem, 0, height);
                        modelData.display(root.barWindow, point.x, point.y);
                    }
                    Image {
                        anchors.centerIn: parent
                        width: 20; height: 20
                        source: trayButton.modelData.icon
                    }
                    TapHandler { acceptedButtons: Qt.RightButton; onTapped: trayButton.showMenu() }
                    Keys.onMenuPressed: showMenu()
                }
            }
        }
    }
}
