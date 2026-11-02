// The content of a preview, shared by the inspector and the expanded view (files-details.html): a picture or a
// PDF's first page (zoomable when `zoomable`: wheel, + / − / 0, drag, double click resets), video or audio on the
// window's single MediaPlayer, code with line numbers, Markdown rendered ⇄ source with links that go somewhere,
// plain text, a broken file, or the file's icon when it has no preview.
import QtQuick
import QtMultimedia
import WysunM3

Item {
    id: root

    property var player                     // the window's MediaPlayer
    property bool zoomable
    property bool showSource
    property real zoom: 1
    readonly property string kind: preview.kind
    readonly property bool picture: (kind === "image" || kind === "pdf") && preview.imageUrl !== "" && preview.error === ""
    readonly property bool media: (kind === "video" || kind === "audio") && preview.mediaUrl !== "" && preview.error === ""
    readonly property bool textual: (kind === "code" || kind === "markdown" || kind === "text") && preview.error === ""
    readonly property alias videoOutput: video
    signal linkActivated(string target)

    function zoomBy(factor) {
        zoom = Math.max(0.1, Math.min(8, zoom * factor));
    }

    function resetZoom() {
        zoom = 1;
        flick.contentX = 0;
        flick.contentY = 0;
    }

    onKindChanged: resetZoom()
    Connections {
        target: preview

        function onChanged() {
            root.resetZoom();
            root.showSource = false;
        }
    }

    // ------------------------------------------------------------------ picture / pdf
    Flickable {
        id: flick

        objectName: "previewPicture"
        visible: root.picture
        anchors.fill: parent
        clip: true
        interactive: root.zoomable && root.zoom > 1
        contentWidth: Math.max(width, image.paintedWidth * root.zoom)
        contentHeight: Math.max(height, image.paintedHeight * root.zoom)
        boundsBehavior: Flickable.StopAtBounds

        Image {
            id: image

            objectName: "previewImage"
            width: flick.width
            height: flick.height
            x: (flick.contentWidth - width) / 2
            y: (flick.contentHeight - height) / 2
            scale: root.zoom
            source: root.picture ? preview.imageUrl : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            autoTransform: true
            smooth: true
            mipmap: true
            sourceSize.width: root.zoomable ? 2400 : 900
            sourceSize.height: root.zoomable ? 2400 : 900
        }

        WheelHandler {
            enabled: root.zoomable
            target: null
            onWheel: event => root.zoomBy(event.angleDelta.y > 0 ? 1.15 : 1 / 1.15)
        }
        TapHandler {
            enabled: root.zoomable
            onDoubleTapped: root.resetZoom()
        }
    }

    // A picture that does not decode (or a broken file of any kind).
    EmptyState {
        objectName: "previewBroken"
        visible: preview.error !== "" || image.status === Image.Error
        anchors.centerIn: parent
        width: parent.width
        emblemShape: "clover"
        icon: root.kind === "image" ? "broken_image" : "error"
        title: ""
        message: preview.error !== "" ? preview.error : "No se pudo abrir la imagen. El archivo sigue seleccionado."
    }

    // ------------------------------------------------------------------ video / audio
    Rectangle {
        visible: root.media
        anchors.fill: parent
        radius: Theme.rounding.large ?? 0
        color: root.kind === "video" ? Theme.m3scrim : Theme.m3surfaceContainerHighest

        // The stopped video shows a frame of it (as the mock-up), not black.
        Image {
            anchors.fill: parent
            visible: root.kind === "video" && root.player && root.player.playbackState === MediaPlayer.StoppedState
            source: visible ? preview.posterUrl : ""
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        VideoOutput {
            id: video

            objectName: "previewVideo"
            anchors.fill: parent
            visible: root.kind === "video"
        }
        ShapeEmblem {
            visible: root.kind === "audio"
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -controls.height / 2
            size: Math.min(parent.width, parent.height) * 0.45
            width: size
            height: size
            shape: "cookie"
            icon: "music_note"
            color: Theme.m3primaryContainer
            iconColor: Theme.m3onPrimaryContainer
        }
        Item {
            id: controls

            anchors.bottom: parent.bottom
            width: parent.width
            height: Metrics.topAppBarSmall

            Rectangle {
                anchors.fill: parent
                radius: Theme.rounding.large ?? 0
                color: Qt.alpha(Theme.m3surfaceContainerHighest, root.kind === "video" ? 0.85 : 0)
            }
            IconButton {
                id: playButton

                objectName: "previewPlay"
                x: Theme.padding.small ?? 0
                anchors.verticalCenter: parent.verticalCenter
                type: "filled"
                icon: root.player && root.player.playbackState === MediaPlayer.PlayingState ? "pause" : "play_arrow"
                onClicked: root.player.playbackState === MediaPlayer.PlayingState ? root.player.pause() : root.player.play()
            }
            Slider {
                anchors.left: playButton.right
                anchors.leftMargin: Theme.spacing.small ?? 0
                anchors.right: time.left
                anchors.rightMargin: Theme.spacing.small ?? 0
                anchors.verticalCenter: parent.verticalCenter
                from: 0
                to: Math.max(1, root.player ? root.player.duration : 1)
                value: root.player ? root.player.position : 0
                onMoved: v => {
                    if (root.player)
                        root.player.position = v;
                }
                // Dragging assigns `value`; follow the player again afterwards.
                onReleased: value = Qt.binding(() => root.player ? root.player.position : 0)
            }
            Label {
                id: time

                anchors.right: parent.right
                anchors.rightMargin: Theme.padding.medium ?? 0
                anchors.verticalCenter: parent.verticalCenter
                role: "label.medium"
                text: {
                    const ms = root.player ? root.player.position : 0;
                    const s = Math.floor(ms / 1000);
                    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
                }
                color: Theme.m3onSurface
            }
        }
    }

    // ------------------------------------------------------------------ text, code, markdown
    Flickable {
        id: textFlick

        objectName: "previewText"
        visible: root.textual
        anchors.fill: parent
        clip: true
        contentWidth: width
        contentHeight: textRow.height
        boundsBehavior: Flickable.StopAtBounds

        Row {
            id: textRow

            width: textFlick.width
            spacing: Theme.spacing.medium ?? 0

            Text {
                id: numbers

                visible: root.kind === "code" || (root.kind === "markdown" && root.showSource)
                text: visible ? Array.from({length: Math.min(preview.lineCount, 20000)}, (_, i) => i + 1).join("\n") : ""
                font.family: Theme.font.family?.mono ?? ""
                font.pointSize: Math.max(1, Theme.typeFont("body.small").pointSize)
                color: Theme.m3outline
                horizontalAlignment: Text.AlignRight
            }
            TextEdit {
                id: body

                objectName: "previewBody"
                width: textRow.width - (numbers.visible ? numbers.width + textRow.spacing : 0)
                readOnly: true
                selectByMouse: true
                wrapMode: root.kind === "code" || root.showSource ? TextEdit.NoWrap : TextEdit.Wrap
                textFormat: (root.kind === "code" || (root.kind === "markdown" && !root.showSource)) ? TextEdit.RichText : TextEdit.PlainText
                text: root.kind === "code" ? preview.html : root.kind === "markdown" && !root.showSource ? preview.html : preview.text
                font.family: root.kind === "markdown" && !root.showSource ? Theme.typeFont("body.medium").family : Theme.font.family?.mono ?? ""
                font.pointSize: Math.max(1, Theme.typeFont(root.kind === "markdown" && !root.showSource ? "body.medium" : "body.small").pointSize)
                color: Theme.m3onSurface
                selectionColor: Theme.m3primary
                selectedTextColor: Theme.m3onPrimary
                onLinkActivated: link => root.linkActivated(link)

                HoverHandler {
                    cursorShape: body.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.IBeamCursor
                }
            }
        }
    }

    // ------------------------------------------------------------------ nothing to show
    Item {
        visible: preview.mode === "file" && root.kind === "" && preview.error === ""
        anchors.fill: parent

        FileIcon {
            anchors.centerIn: parent
            width: Math.min(parent.width, parent.height) * 0.45
            height: width
            kind: preview.fileKind
            icon: preview.icon
            badge: preview.badge
            role: preview.role
        }
    }
    Item {
        visible: preview.mode === "folder" || preview.mode === "multi"
        anchors.fill: parent

        ShapeEmblem {
            anchors.centerIn: parent
            size: Math.min(parent.width, parent.height) * 0.5
            width: size
            height: size
            shape: preview.mode === "folder" ? "cookie" : "clover"
            icon: preview.mode === "folder" ? "folder" : "select_all"
            color: Theme.m3secondaryContainer
            iconColor: Theme.m3onSecondaryContainer
        }
    }

    CircularProgress {
        anchors.centerIn: parent
        visible: preview.loading
        indeterminate: true
    }
}
