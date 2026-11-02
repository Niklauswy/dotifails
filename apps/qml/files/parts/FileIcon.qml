// The icon of a file as the mock-ups draw it: a folder is its silhouette (tab and body) with a glyph when it is
// special; images and videos show their thumbnail with rounded corners (a video adds a play badge and its length);
// a song shows its cover in a cookie; documents are a sheet with a folded corner, their first lines (or a glyph)
// and the extension on a band of their colour role. Thumbnails arrive later: the mask is always a layer, so a
// picture that comes in after the icon was built still shows. Under the software scene graph (offscreen tests),
// which cannot run the mask shader, the picture shows unmasked.
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import WysunM3

Item {
    id: root

    property string kind: "other"           // folder image video audio pdf md doc code archive other
    property string icon: "draft"
    property string glyph
    property string badge
    property string role: "primary"
    property url thumb
    property string duration
    property var snippet: []
    property bool compact                   // list rows: no snippet, smaller band
    readonly property bool _software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool media: kind === "image" || kind === "video"
    readonly property bool hasThumb: picture.status === Image.Ready
    readonly property color roleColor: role === "error" ? Theme.m3error : role === "tertiary" ? Theme.m3tertiary : role === "secondary" ? Theme.m3secondary : Theme.m3primary
    readonly property color onRoleColor: role === "error" ? Theme.m3onError : role === "tertiary" ? Theme.m3onTertiary : role === "secondary" ? Theme.m3onSecondary : Theme.m3onPrimary

    implicitWidth: FilesMetrics.tileIcon
    implicitHeight: FilesMetrics.tileIcon

    // ---------------------------------------------------------------- folder
    Item {
        id: folder

        visible: root.kind === "folder"
        anchors.centerIn: parent
        width: parent.width
        height: parent.height * 0.8

        Rectangle {
            width: parent.width * 0.42
            height: parent.height * 0.3
            radius: Math.min(height / 2, Theme.rounding.small ?? 0)
            color: root.glyph !== "" ? Theme.m3secondary : Theme.m3outlineVariant
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: parent.height * 0.84
            radius: Math.min(height / 3, Theme.rounding.medium ?? 0)
            color: root.glyph !== "" ? Theme.m3secondaryContainer : Theme.m3surfaceContainerHighest

            Icon {
                anchors.centerIn: parent
                visible: root.glyph !== ""
                name: root.glyph
                filled: true
                size: Math.round(parent.height * 0.46)
                color: Theme.m3onSecondaryContainer
            }
        }
    }

    // ---------------------------------------------------------------- image / video
    Image {
        id: picture

        source: root.media || root.kind === "audio" ? root.thumb : ""
        asynchronous: true
        autoTransform: true
        cache: true
        visible: false
        sourceSize.width: 256
        sourceSize.height: 256
    }

    Item {
        id: frame

        readonly property real ratio: root.hasThumb && picture.implicitHeight > 0 ? Math.max(0.66, Math.min(1.6, picture.implicitWidth / picture.implicitHeight)) : 1

        visible: root.media
        anchors.centerIn: parent
        width: ratio >= 1 ? root.width : root.height * ratio
        height: ratio >= 1 ? root.width / ratio : root.height

        Rectangle {
            anchors.fill: parent
            visible: !root.hasThumb
            radius: Theme.rounding.medium ?? 0
            color: Theme.m3surfaceContainerHighest

            Icon {
                anchors.centerIn: parent
                name: root.icon
                size: Math.round(parent.height * 0.42)
                color: Theme.m3onSurfaceVariant
            }
        }
        Image {
            id: cropped

            anchors.fill: parent
            source: root.hasThumb ? root.thumb : ""
            asynchronous: true
            autoTransform: true
            fillMode: Image.PreserveAspectCrop
            sourceSize.width: 256
            sourceSize.height: 256
            visible: root.hasThumb && root._software
        }
        Rectangle {
            id: roundMask

            anchors.fill: parent
            radius: root.compact ? (Theme.rounding.small ?? 0) : (Theme.rounding.medium ?? 0)
            color: Theme.m3onSurface
            layer.enabled: !root._software       // always a layer (see the header)
            layer.smooth: true
            visible: false
        }
        MultiEffect {
            anchors.fill: parent
            visible: root.hasThumb && !root._software
            source: cropped
            maskEnabled: true
            maskSource: roundMask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
            autoPaddingEnabled: false
        }
        Rectangle {
            visible: root.kind === "video" && !root.compact
            anchors.centerIn: parent
            width: Math.round(parent.height * 0.36)
            height: width
            radius: width / 2
            color: Qt.alpha(Theme.m3scrim, 0.45)

            Icon {
                anchors.centerIn: parent
                name: "play_arrow"
                filled: true
                size: Math.round(parent.width * 0.7)
                color: Theme.m3inverseOnSurface
            }
        }
        Rectangle {
            visible: root.kind === "video" && root.duration !== "" && !root.compact
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Theme.spacing.extraSmall ?? 0
            width: durationLabel.implicitWidth + 2 * (Theme.spacing.small ?? 0)
            height: durationLabel.implicitHeight + (Theme.spacing.extraSmall ?? 0)
            radius: height / 2
            color: Qt.alpha(Theme.m3scrim, 0.6)

            Label {
                id: durationLabel

                anchors.centerIn: parent
                role: "label.small"
                text: root.duration
                color: Theme.m3inverseOnSurface
            }
        }
    }

    // ---------------------------------------------------------------- audio
    Item {
        visible: root.kind === "audio"
        anchors.centerIn: parent
        width: Math.min(root.width, root.height) * (root.compact ? 1 : 0.86)
        height: width

        ShapeEmblem {
            anchors.fill: parent
            size: parent.width
            shape: "cookie"
            visible: !root.hasThumb || root._software
            color: Theme.m3primaryContainer
            icon: root.hasThumb ? "" : "music_note"
            iconColor: Theme.m3onPrimaryContainer
        }
        Image {
            anchors.fill: parent
            source: root.kind === "audio" && root.hasThumb ? root.thumb : ""
            visible: root.hasThumb && root._software
            fillMode: Image.PreserveAspectCrop
            sourceSize.width: 256
            sourceSize.height: 256
        }
        ShapeEmblem {
            id: cookieMask

            anchors.fill: parent
            size: parent.width
            shape: "cookie"
            color: Theme.m3onSurface
            layer.enabled: !root._software
            layer.smooth: true
            visible: false
        }
        MultiEffect {
            anchors.fill: parent
            visible: root.kind === "audio" && root.hasThumb && !root._software
            source: picture
            maskEnabled: true
            maskSource: cookieMask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
            autoPaddingEnabled: false
        }
    }

    // ---------------------------------------------------------------- documents
    Item {
        id: sheet

        readonly property real fold: width * 0.26
        readonly property bool lines: !root.compact && (root.snippet?.length ?? 0) > 0

        visible: !root.media && root.kind !== "folder" && root.kind !== "audio"
        anchors.centerIn: parent
        height: parent.height
        width: Math.round(height * 0.76)

        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeWidth: -1
                fillColor: Theme.m3surfaceContainerHighest
                startX: Theme.rounding.small ?? 0
                startY: 0
                PathLine { x: sheet.width - sheet.fold; y: 0 }
                PathLine { x: sheet.width; y: sheet.fold }
                PathLine { x: sheet.width; y: sheet.height - (Theme.rounding.small ?? 0) }
                PathArc { x: sheet.width - (Theme.rounding.small ?? 0); y: sheet.height; radiusX: Theme.rounding.small ?? 0; radiusY: Theme.rounding.small ?? 0 }
                PathLine { x: Theme.rounding.small ?? 0; y: sheet.height }
                PathArc { x: 0; y: sheet.height - (Theme.rounding.small ?? 0); radiusX: Theme.rounding.small ?? 0; radiusY: Theme.rounding.small ?? 0 }
                PathLine { x: 0; y: Theme.rounding.small ?? 0 }
                PathArc { x: Theme.rounding.small ?? 0; y: 0; radiusX: Theme.rounding.small ?? 0; radiusY: Theme.rounding.small ?? 0 }
            }
            ShapePath {
                strokeWidth: -1
                fillColor: Theme.m3outlineVariant
                startX: sheet.width - sheet.fold
                startY: 0
                PathLine { x: sheet.width - sheet.fold; y: sheet.fold * 0.7 }
                PathArc { x: sheet.width - sheet.fold * 0.7; y: sheet.fold; radiusX: sheet.fold * 0.3; radiusY: sheet.fold * 0.3; direction: PathArc.Counterclockwise }
                PathLine { x: sheet.width; y: sheet.fold }
            }
        }

        Column {
            visible: sheet.lines
            x: sheet.width * 0.12
            y: sheet.fold * 0.75
            width: sheet.width - sheet.fold - x
            spacing: 0
            clip: true

            Repeater {
                model: sheet.lines ? root.snippet : []

                Text {
                    required property string modelData

                    width: sheet.width * 0.8
                    text: modelData === "" ? " " : modelData
                    font.family: Theme.font.family?.mono ?? ""
                    font.pixelSize: Math.max(4, Math.round(sheet.height * 0.062))
                    color: Theme.m3onSurfaceVariant
                    elide: Text.ElideNone
                    clip: true
                    renderType: Text.QtRendering
                }
            }
        }

        Icon {
            visible: !sheet.lines
            anchors.centerIn: parent
            name: root.icon
            size: Math.round(sheet.width * 0.42)
            color: Theme.m3onSurfaceVariant
        }

        Rectangle {
            visible: root.badge !== ""
            x: root.compact ? -Math.round(width * 0.2) : -(Theme.spacing.extraSmall ?? 0)
            anchors.bottom: parent.bottom
            anchors.bottomMargin: root.compact ? -(Theme.spacing.extraSmall ?? 0) : sheet.height * 0.12
            width: band.implicitWidth + (root.compact ? 4 : 2 * (Theme.spacing.small ?? 0))
            height: band.implicitHeight + (root.compact ? 0 : 2)
            radius: Theme.rounding.extraSmall ?? 0
            color: root.roleColor

            Text {
                id: band

                anchors.centerIn: parent
                text: root.badge
                font.family: Theme.typeFont("label.small").family
                font.weight: Font.Bold
                font.pixelSize: root.compact ? Math.max(6, Math.round(root.height * 0.22)) : Math.max(7, Math.round(sheet.height * 0.13))
                color: root.onRoleColor
            }
        }
    }
}
