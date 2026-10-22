// A wallpaper surface: still images and video through Visual, GIFs through AnimatedImage.
import QtQuick
import Wysun.Multimedia
import qs.services

Item {
    id: root

    property string source
    property bool playing: true
    property bool animate: true
    property int fillMode: VisualSource.PreserveAspectCrop
    readonly property bool isGif: source.toLowerCase().endsWith(".gif")
    readonly property bool ready: isGif ? gif.status === Image.Ready : visual.ready

    Visual {
        id: visual

        anchors.fill: parent
        visible: !root.isGif
        source: root.isGif ? "" : root.source
        playing: root.playing
        animate: root.animate
        fillMode: root.fillMode
    }

    AnimatedImage {
        id: gif

        anchors.fill: parent
        visible: root.isGif
        source: root.isGif ? `file://${root.source}` : ""
        playing: root.playing
        asynchronous: true
        cache: false
        fillMode: Image.PreserveAspectCrop
    }
}
