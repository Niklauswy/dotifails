// Synced lyrics, big: the current line lit, the rest fading with their distance; the view follows the song
// smoothly and leaves the reader alone for 3.5 s after a wheel scroll. Click a line (or ↑/↓ and Enter) to jump
// there. Plain lyrics just scroll; without lyrics a state message shows.
import QtQuick
import WysunM3
import "parts"

FocusScope {
    id: root

    readonly property bool synced: lyrics.state === "synced"
    property int cursor: -1
    property bool holding

    ListView {
        id: view

        objectName: "lyricLines"
        anchors.fill: parent
        visible: lyrics.hasLyrics
        focus: true
        model: lyrics.lines
        clip: true
        spacing: root.synced ? Theme.spacing.large ?? 0 : Theme.spacing.small ?? 0
        boundsBehavior: Flickable.StopAtBounds
        currentIndex: root.cursor >= 0 ? root.cursor : lyrics.currentIndex
        highlightRangeMode: root.synced && !root.holding ? ListView.ApplyRange : ListView.NoHighlightRange
        preferredHighlightBegin: height * 0.3
        preferredHighlightEnd: height * 0.3 + MusicMetrics.trackRow
        highlightMoveDuration: Motion.ms("slowSpatial")
        header: Item {
            height: root.synced ? view.height * 0.3 : 0
        }
        footer: Item {
            height: view.height * 0.6
        }

        Keys.onUpPressed: root.cursor = Math.max(0, (root.cursor >= 0 ? root.cursor : lyrics.currentIndex) - 1)
        Keys.onDownPressed: root.cursor = Math.min(view.count - 1, (root.cursor >= 0 ? root.cursor : lyrics.currentIndex) + 1)
        Keys.onReturnPressed: {
            if (root.cursor >= 0)
                lyrics.seekLine(root.cursor);
            root.cursor = -1;
        }
        Keys.onEscapePressed: event => {
            if (root.cursor < 0) {
                event.accepted = false;
                return;
            }
            root.cursor = -1;
        }

        WheelHandler {
            onWheel: {
                root.holding = true;
                hold.restart();
            }
        }

        delegate: Label {
            id: line

            required property var modelData
            required property int index
            readonly property int distance: Math.abs(index - lyrics.currentIndex)
            readonly property bool lit: root.synced && index === lyrics.currentIndex

            objectName: lit ? "currentLyric" : ""
            width: view.width
            role: root.synced ? "headline.small" : "title.medium"
            text: modelData.text
            wrapMode: Text.Wrap
            color: lit ? Theme.m3onSurface : root.cursor === index ? Theme.m3primary : Theme.m3onSurfaceVariant
            opacity: !root.synced ? 1 : lit ? 1 : Math.max(0.35, 1 - distance * 0.18)
            scale: lit ? 1 : 0.96
            transformOrigin: Item.Left

            SpringBehavior on scale {
                kind: "defaultSpatial"
            }
            Behavior on color {
                CAnim {
                    kind: "defaultEffects"
                }
            }

            MouseArea {
                anchors.fill: parent
                enabled: root.synced
                cursorShape: Qt.PointingHandCursor
                onClicked: lyrics.seekLine(line.index)
            }
        }
    }

    Timer {
        id: hold

        interval: Theme.duration("extraLarge") * 3.5
        onTriggered: root.holding = false
    }

    EmptyState {
        anchors.fill: parent
        visible: !lyrics.hasLyrics
        emblemShape: lyrics.state === "instrumental" ? "flower" : "clover"
        icon: lyrics.state === "loading" ? "hourglass_top" : lyrics.state === "instrumental" ? "piano" : "lyrics"
        title: lyrics.state === "instrumental" ? "Instrumental" : lyrics.state === "loading" ? "Buscando letra…" : "Sin letra"
        message: lyrics.state === "missing" ? "Solo se muestran letras que coinciden en título, artista y duración (±2 s)." : lyrics.state === "idle" ? lyrics.message : ""
    }
}
