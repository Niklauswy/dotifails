// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// modules/background/{Background,Wallpaper,DesktopClock}.qml, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "BackgroundPolicy.js" as Policy
import "../../Logic.js" as Logic
import "../../" as Wysun

Item {
    id: root
    required property var preferences
    required property string outputName
    property bool fullscreen: false
    property real pixelRatio: 1
    readonly property var wallpaper: Logic.wallpaper(preferences.environment, outputName, preferences.home, Wysun.Appearance.wallpaper)
    readonly property var clockSettings: Policy.clockSettings(preferences.environment, outputName, fullscreen)

    Wallpaper {
        anchors.fill: parent
        path: root.wallpaper.path
        mode: root.wallpaper.mode
        pixelRatio: root.pixelRatio
    }
    Loader {
        id: clockLoader
        objectName: "desktopClockLoader"
        active: root.clockSettings.enabled
        asynchronous: true
        width: Math.min(implicitWidth, Math.max(0, root.width - Wysun.Appearance.spaceL * 2))
        height: Math.min(implicitHeight, Math.max(0, root.height - Wysun.Appearance.spaceL * 2))
        readonly property var placement: Policy.position(root.width, root.height, width, height,
            Wysun.Appearance.railWidth + Wysun.Appearance.spaceXl, root.clockSettings.position)
        x: placement.x
        y: placement.y
        sourceComponent: DesktopClock {
            Time { id: clock }
            now: clock.date
        }
    }
}
