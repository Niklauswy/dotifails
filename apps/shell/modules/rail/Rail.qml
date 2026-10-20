// Adaptado de caelestia-dots/shell/modules/bar/Bar.qml (GPL-3.0), modificado para Wysun.
// Fuente: caelestia-dots/shell, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Véanse LICENSES/GPL-3.0.txt y THIRD_PARTY.md.
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray
import Quickshell.Services.UPower
import "../../Logic.js" as Logic
import "../../" as Wysun

PanelWindow {
    id: root
    required property var preferences
    required property var controller
    required property var clock
    required property var motion
    required property var outputs
    required property var modelData

    screen: modelData
    readonly property var monitor: outputs.monitorFor(modelData)
    readonly property bool fullscreen: outputs.isFullscreen(modelData)
    readonly property var workspaces: monitor
        ? Logic.sortWorkspaces(Hyprland.workspaces.values.filter(w => w.monitor === monitor && !String(w.name).startsWith("special:")))
        : []
    readonly property bool trayOwner: outputs.trayOwner(preferences) === modelData.name
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property string activeTitle: Hyprland.activeToplevel?.monitor === monitor ? Hyprland.activeToplevel.title : "Escritorio"
    readonly property int volumePercent: sink?.audio ? Math.round(sink.audio.volume * 100) : -1

    visible: Logic.monitorEnabled(preferences.environment, modelData.name, preferences.nativeBarData) && !fullscreen
    anchors { top: true; bottom: true; left: true }
    margins { left: 0 }
    implicitWidth: Wysun.Appearance.railWidth
    exclusiveZone: implicitWidth
    color: "transparent"
    WlrLayershell.namespace: "wysun-rail"
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    PwObjectTracker { objects: root.sink ? [root.sink] : [] }

    RailContent {
        anchors.fill: parent
        controller: root.controller
        clock: root.clock
        motion: root.motion
        screenName: root.modelData.name
        activeTitle: root.activeTitle
        workspaces: root.workspaces
        trayOwner: root.trayOwner
        trayItems: SystemTray.items
        trayWindow: root
        sink: root.sink
        volumePercent: root.volumePercent
        hasBattery: UPower.displayDevice.ready && UPower.displayDevice.isLaptopBattery
        batteryPercentage: UPower.displayDevice.percentage
    }
}
