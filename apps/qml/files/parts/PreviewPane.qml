// The content of a preview, shared by the inspector and the expanded view (files-details.html): a picture or a
// PDF's first page (zoomable when `zoomable`: wheel, + / − / 0, drag, double click resets), video or audio on the
// window's single MediaPlayer, code with line numbers, Markdown rendered ⇄ source with links that go somewhere,
// plain text, a broken file, or the file's icon when it has no preview.
import QtQuick
import QtMultimedia
import QtQuick.Effects
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

    // The pages of a PDF.
    Rectangle {
        objectName: "pdfPager"
        visible: root.kind === "pdf" && preview.pages > 1 && root.picture
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.spacing.small ?? 0
        width: pager.implicitWidth + 2 * (Theme.spacing.extraSmall ?? 0)
        height: Metrics.iconButtonSize
        radius: height / 2
        color: Theme.m3surfaceContainerHighest

        Row {
            id: pager

            anchors.centerIn: parent

            IconButton {
                objectName: "pdfPrevious"
                icon: "chevron_left"
                disabled: preview.page <= 1
                onClicked: preview.setPage(preview.page - 1)
            }
            Label {
                anchors.verticalCenter: parent.verticalCenter
                role: "label.large"
                text: preview.page + " / " + preview.pages
                color: Theme.m3onSurface
            }
            IconButton {
                objectName: "pdfNext"
                icon: "chevron_right"
                disabled: preview.page >= preview.pages
                onClicked: preview.setPage(preview.page + 1)
            }
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
    Item {
        visible: root.media
        anchors.fill: parent

        // The cover, blurred, behind a song. Without the shader (software scene graph) there is just the panel.
        Image {
            id: ambientSource

            anchors.fill: parent
            visible: false
            source: root.kind === "audio" ? preview.posterUrl : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize.width: 256
            sourceSize.height: 256
        }
        MultiEffect {
            anchors.fill: parent
            visible: root.kind === "audio" && ambientSource.status === Image.Ready && GraphicsInfo.api !== GraphicsInfo.Software
            source: ambientSource
            blurEnabled: true
            blur: 1
            blurMax: 64
            opacity: 0.35
        }

        Column {
            id: songText

            visible: root.kind === "audio"
            anchors.bottom: transport.top
            anchors.bottomMargin: Theme.spacing.medium ?? 0
            x: Theme.padding.large ?? 0
            width: parent.width - 2 * x
            spacing: Theme.spacing.extraSmall ?? 0

            Label {
                objectName: "songTitle"
                width: parent.width
                role: "title.large"
                text: preview.mediaTitle !== "" ? preview.mediaTitle : preview.name
                color: Theme.m3onSurface
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
            Label {
                visible: text !== ""
                width: parent.width
                role: "body.medium"
                text: preview.mediaArtist
                color: Theme.m3onSurfaceVariant
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }

        // The picture: the video itself, or the song's cover as large as it fits.
        Item {
            id: stage

            anchors.top: parent.top
            anchors.topMargin: root.kind === "audio" ? (Theme.padding.large ?? 0) : 0
            anchors.bottom: root.kind === "audio" ? songText.top : transport.top
            anchors.bottomMargin: Theme.spacing.medium ?? 0
            width: parent.width

            Rectangle {
                visible: root.kind === "video"
                anchors.fill: parent
                radius: Theme.rounding.large ?? 0
                color: Theme.m3scrim

                // A stopped video shows a frame of it, not black.
                Image {
                    anchors.fill: parent
                    visible: root.player && root.player.playbackState === MediaPlayer.StoppedState
                    source: visible ? preview.posterUrl : ""
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
                VideoOutput {
                    id: video

                    objectName: "previewVideo"
                    anchors.fill: parent
                }
                TapHandler {
                    onTapped: transport.playing ? root.player.pause() : root.player.play()
                }
            }

            Item {
                visible: root.kind === "audio"
                anchors.centerIn: parent
                width: Math.max(1, Math.min(parent.width - 2 * (Theme.padding.large ?? 0), parent.height))
                height: width

                ShapeEmblem {
                    anchors.centerIn: parent
                    visible: !cover.ready
                    size: parent.width * 0.8
                    width: size
                    height: size
                    shape: "cookie"
                    icon: "music_note"
                    color: Theme.m3primaryContainer
                    iconColor: Theme.m3onPrimaryContainer
                }
                Image {
                    id: cover

                    readonly property bool ready: status === Image.Ready

                    objectName: "songCover"
                    anchors.fill: parent
                    source: root.kind === "audio" ? preview.posterUrl : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    sourceSize.width: 512
                    sourceSize.height: 512
                    visible: ready && GraphicsInfo.api === GraphicsInfo.Software
                }
                Rectangle {
                    id: coverMask

                    anchors.fill: parent
                    radius: Theme.rounding.extraLarge ?? 0
                    color: Theme.m3onSurface
                    layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software      // always a layer: covers arrive late
                    layer.smooth: true
                    visible: false
                }
                MultiEffect {
                    anchors.fill: parent
                    visible: cover.ready && GraphicsInfo.api !== GraphicsInfo.Software
                    source: cover
                    maskEnabled: true
                    maskSource: coverMask
                    maskThresholdMin: 0.5
                    maskSpreadAtMin: 1.0
                    autoPaddingEnabled: false
                }
            }
        }

        MediaControls {
            id: transport

            anchors.bottom: parent.bottom
            x: Theme.padding.small ?? 0
            width: parent.width - 2 * x
            player: root.player
            wavy: root.kind === "audio"
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
