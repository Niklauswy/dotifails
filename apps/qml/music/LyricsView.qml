// Synced lyrics, big: the current line lit and filled karaoke-style as it is sung, glowing in the record's colour;
// the rest shrink, fade and blur with their distance; the view follows the song
// smoothly and leaves the reader alone for 3.5 s after a wheel scroll. Click a line (or ↑/↓ and Enter) to jump
// there. Plain lyrics just scroll; without lyrics a state message shows.
import QtQuick
import QtQuick.Effects
import WysunM3
import "parts"

FocusScope {
    id: root

    readonly property bool synced: lyrics.state === "synced"
    property int cursor: -1
    property bool holding
    property color glow: Theme.m3primary
    readonly property bool _software: GraphicsInfo.api === GraphicsInfo.Software

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

        delegate: Item {
            id: line

            required property var modelData
            required property int index
            readonly property int distance: Math.abs(index - lyrics.currentIndex)
            readonly property bool lit: root.synced && index === lyrics.currentIndex
            readonly property bool sung: root.synced && index < lyrics.currentIndex
            // How far through the lit line the song is (karaoke fill), from its time to the next line's.
            readonly property real fill: {
                if (!lit)
                    return sung ? 1 : 0;
                const next = lyrics.lines[index + 1];
                const start = modelData.time;
                const end = next ? next.time : start + 4;
                return Math.max(0, Math.min(1, (player.position + lyrics.offset - start) / Math.max(0.5, end - start)));
            }

            objectName: lit ? "currentLyric" : ""
            width: view.width
            height: base.implicitHeight * (lit ? 1 : 0.8)
            opacity: !root.synced ? 1 : lit ? 1 : sung ? Math.max(0.3, 0.7 - distance * 0.1) : Math.max(0.25, 0.85 - distance * 0.15)

            Behavior on height {
                Anim {
                    kind: "defaultSpatial"
                }
            }
            Behavior on opacity {
                Anim {
                    kind: "slowEffects"
                }
            }

            Item {
                id: body

                width: parent.width
                height: base.implicitHeight
                scale: line.lit ? 1 : root.synced ? 0.8 : 1
                transformOrigin: Item.TopLeft
                // Lines away from the one being sung go softly out of focus; the lit one glows in the record's
                // colour.
                layer.enabled: root.synced && !root._software && (line.lit || line.distance >= 2)
                layer.effect: MultiEffect {
                    blurEnabled: !line.lit
                    blur: Math.min(0.5, (line.distance - 1) * 0.1)
                    blurMax: 32
                    shadowEnabled: line.lit
                    shadowBlur: 1
                    shadowScale: 1.02
                    shadowColor: Qt.alpha(root.glow, 0.55)
                    shadowHorizontalOffset: 0
                    shadowVerticalOffset: 0
                    autoPaddingEnabled: true
                }

                SpringBehavior on scale {
                    kind: "defaultSpatial"
                }

                Label {
                    id: base

                    width: line.width
                    role: root.synced ? "headline.large" : "title.large"
                    font.weight: Font.Bold
                    text: line.modelData.text
                    wrapMode: Text.Wrap
                    color: root.cursor === line.index ? Theme.m3primary : line.sung ? Theme.m3onSurface : Theme.m3onSurfaceVariant
                }

                // The sung part of the lit line, painted over it from the left as the song moves on.
                Item {
                    visible: line.lit
                    width: base.width * fillAmount.value
                    height: base.height
                    clip: true

                    QtObject {
                        id: fillAmount

                        property real value: line.fill

                        Behavior on value {
                            enabled: line.lit && !Motion.reduced
                            NumberAnimation {
                                duration: 260
                            }
                        }
                    }

                    Label {
                        width: base.width
                        role: base.role
                        font.weight: Font.Bold
                        text: base.text
                        wrapMode: Text.Wrap
                        color: Theme.m3onSurface
                    }
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
