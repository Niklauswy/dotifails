// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// modules/background/Wallpaper.qml y services/Wallpapers.qml, commit
// 507d66285e9d9fde9330adc64159cfdebb28c19a. Véanse THIRD_PARTY.md y LICENSES/GPL-3.0.txt.
import QtQuick
import "BackgroundPolicy.js" as Policy
import "../../" as Wysun

Rectangle {
    id: root
    property string path: ""
    property string mode: "fill"
    property real pixelRatio: 1
    readonly property alias status: image.status
    color: Wysun.Appearance.canvas

    // A static image with no shader capture, transition render loop or video.
    Image {
        id: image
        objectName: "wallpaperImage"
        anchors.fill: parent
        source: Policy.localUrl(root.path)
        asynchronous: true
        cache: false
        sourceSize.width: Math.ceil(root.width * root.pixelRatio)
        sourceSize.height: Math.ceil(root.height * root.pixelRatio)
        fillMode: ({ fill: Image.PreserveAspectCrop, fit: Image.PreserveAspectFit,
                     stretch: Image.Stretch, center: Image.Pad })[root.mode] ?? Image.PreserveAspectCrop
        visible: status === Image.Ready
    }
}
