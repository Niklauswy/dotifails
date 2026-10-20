// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun
// Origen: modules/drawers/Panels.qml; services/Players.qml, commit 507d66285e9d9fde9330adc64159cfdebb28c19a.
// Avisos y licencia íntegra: THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import Quickshell.Hyprland
import "services" as Services
import "Logic.js" as Logic

// Providers are created only while the surface is visible. Closing the popout
// destroys this object, so MPRIS, /proc sampling and df stop instead of
// polling in the background.
Item {
    id: root
    property bool enabled: false
    property string monitorName: ""
    readonly property alias metrics: metrics
    readonly property alias media: media
    readonly property var workspaces: Logic.desktops(Hyprland.workspaces.values, monitorName)
    readonly property var windows: Hyprland.toplevels.values
    Services.Metrics { id: metrics; enabled: root.enabled }
    Services.Media { id: media }
}
