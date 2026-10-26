// Artwork in an M3 Expressive shape: the image is masked by a ShapeEmblem (cookie, squircle, circle, flower…);
// without an image the shape shows a placeholder icon on its container colour. `spinning` slowly turns the
// shape (not the picture) while music plays; reduced motion keeps it still. Under the software scene graph,
// which cannot run the mask shader, the picture shows as it is.
import QtQuick
import QtQuick.Effects
import WysunM3

Item {
    id: root

    property url source
    // Four sources make a 2×2 mosaic (a playlist made of its songs' covers); one is used like `source`.
    property var sources: []
    readonly property url _single: sources && sources.length > 0 && sources.length < 4 ? sources[0] : source
    readonly property bool _mosaic: sources && sources.length >= 4
    property string shape: "squircle"
    property string placeholderIcon: "music_note"
    property color fill: Theme.m3surfaceContainerHighest
    property color placeholderColor: Theme.m3onSurfaceVariant
    property bool spinning
    property string initials
    readonly property bool hasImage: _mosaic ? mosaic.ready : image.status === Image.Ready
    readonly property bool _software: GraphicsInfo.api === GraphicsInfo.Software

    implicitWidth: Metrics.listImageSize
    implicitHeight: Metrics.listImageSize

    ShapeEmblem {
        id: emblem

        anchors.fill: parent
        size: Math.min(parent.width, parent.height)
        shape: root.shape
        color: root.fill
        icon: root.hasImage || root.initials !== "" ? "" : root.placeholderIcon
        iconColor: root.placeholderColor
        visible: !root.hasImage
        rotation: spin.angle

        Text {
            anchors.centerIn: parent
            visible: root.initials !== "" && !root.hasImage
            font.family: Theme.typeFont("headline.large").family
            font.weight: Theme.typeFont("headline.large").weight
            font.pixelSize: Math.max(1, parent.height * 0.36)
            text: root.initials
            color: root.placeholderColor
            rotation: -parent.rotation
        }
    }

    Image {
        id: image

        anchors.fill: parent
        source: root._mosaic ? "" : root._single
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: width * 2
        sourceSize.height: height * 2
        visible: root.hasImage && root._software && !root._mosaic
    }

    Grid {
        id: mosaic

        readonly property bool ready: {
            let loaded = 0;
            for (let i = 0; i < tiles.count; ++i)
                loaded += tiles.itemAt(i)?.status === Image.Ready ? 1 : 0;
            return root._mosaic && loaded === 4;
        }

        anchors.fill: parent
        columns: 2
        visible: root._mosaic && root.hasImage && root._software

        Repeater {
            id: tiles

            model: root._mosaic ? root.sources.slice(0, 4) : []

            Image {
                required property url modelData

                width: mosaic.width / 2
                height: mosaic.height / 2
                source: modelData
                asynchronous: true
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: width * 2
                sourceSize.height: height * 2
            }
        }
    }

    // The mask: an opaque copy of the shape, rendered off screen.
    ShapeEmblem {
        id: maskShape

        anchors.fill: parent
        size: Math.min(parent.width, parent.height)
        shape: root.shape
        color: Theme.m3onSurface
        layer.enabled: root.hasImage && !root._software
        visible: false
        rotation: spin.angle
    }

    MultiEffect {
        anchors.fill: parent
        visible: root.hasImage && !root._software
        source: root._mosaic ? mosaic : image
        maskEnabled: true
        maskSource: maskShape
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
    }

    QtObject {
        id: spin

        property real angle: 0
    }

    NumberAnimation {
        target: spin
        property: "angle"
        from: spin.angle % 360
        to: spin.angle % 360 + 360
        duration: Theme.duration("extraLarge") * 24
        loops: Animation.Infinite
        running: root.spinning && root.visible && !Motion.reduced
    }
}
