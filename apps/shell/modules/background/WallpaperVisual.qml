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
    // Visual reports its own readiness; for GIFs it is tracked here. It drops on every source
    // change and only rises again from a deferred call, because a cached GIF is Ready synchronously
    // and the wallpaper transition needs to see a false -> true edge.
    readonly property bool ready: isGif ? gifReady : visual.ready
    property bool gifReady

    onSourceChanged: {
        gifReady = false;
        Qt.callLater(refreshGif);
    }

    function refreshGif(): void {
        gifReady = isGif && gif.status === Image.Ready;
    }

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
        onStatusChanged: Qt.callLater(root.refreshGif)
    }
}
