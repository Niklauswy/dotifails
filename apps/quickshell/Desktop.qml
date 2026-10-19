import QtQuick
import Quickshell
import Quickshell.Wayland
import "Logic.js" as Logic

PanelWindow {
    id: desktop
    required property var preferences
    required property var modelData
    screen: modelData
    anchors { top: true; bottom: true; left: true; right: true }
    color: preferences.palette.background
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.namespace: "wysun-desktop"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    // A wallpaper never consumes desktop clicks or keyboard focus.
    mask: Region {}
    readonly property var wallpaper: Logic.wallpaper(preferences.environment, modelData.name, preferences.home, preferences.palette.wallpaper)
    Image {
        anchors.fill: parent
        source: desktop.wallpaper.path ? "file://" + encodeURI(desktop.wallpaper.path).replace(/#/g, "%23").replace(/\?/g, "%3F") : ""
        asynchronous: true
        cache: false
        sourceSize.width: Math.ceil(desktop.width * desktop.modelData.devicePixelRatio)
        sourceSize.height: Math.ceil(desktop.height * desktop.modelData.devicePixelRatio)
        fillMode: ({ fill: Image.PreserveAspectCrop, fit: Image.PreserveAspectFit, stretch: Image.Stretch, center: Image.Pad })[desktop.wallpaper.mode]
    }
}
