// The floating control bar (an M3 floating toolbar): for video and audio, the time and seek row and the transport
// with volume, speed, tracks, more and full screen; for pictures, previous/next, zoom, rotation and the animation.
// Narrow bars (`compact`) fold volume, speed, tracks and ±10 s into «more».
import QtQuick
import WysunM3

Surface {
    id: root

    property var player
    property var image                    // the ImageStage
    readonly property string kind: player ? player.kindName : ""
    readonly property bool timed: kind === "video" || kind === "audio"
    readonly property bool compact: width < Metrics.iconButtonSize * 11
    readonly property bool playing: player !== null && player.state === "playing"
    readonly property Item moreButton: more
    readonly property Item speedButton: speed
    readonly property Item subtitlesButton: subtitles
    readonly property Item audioButton: audio

    signal menuRequested(string which, Item anchor)

    function clock(seconds) {
        return seek.clock(seconds);
    }

    container: Theme.m3surfaceContainer
    color: container
    level: 2
    radius: Theme.rounding.extraLarge ?? 0
    implicitHeight: column.implicitHeight + 2 * (Theme.padding.small ?? 0)

    Column {
        id: column

        anchors.fill: parent
        anchors.leftMargin: Theme.padding.medium ?? 0
        anchors.rightMargin: Theme.padding.medium ?? 0
        anchors.topMargin: Theme.padding.small ?? 0
        anchors.bottomMargin: Theme.padding.small ?? 0
        spacing: 0

        Row {
            id: progress

            visible: root.timed
            width: parent.width
            spacing: Theme.spacing.small ?? 0

            Label {
                id: elapsed

                objectName: "elapsed"
                anchors.verticalCenter: parent.verticalCenter
                role: "label.medium"
                color: Theme.m3onSurfaceVariant
                font.features: ({tnum: 1})
                text: root.clock(root.player ? root.player.position : 0)
            }
            SeekBar {
                id: seek

                width: parent.width - elapsed.width - remaining.width - 2 * parent.spacing
                duration: root.player ? root.player.duration : 0
                position: root.player ? root.player.position : 0
                chapters: root.player ? root.player.chapters : []
                abLoop: root.player ? root.player.abLoop : []
                onScrubbed: s => root.player.scrub(s)
                onSeekRequested: s => root.player.seek(s)
            }
            Label {
                id: remaining

                objectName: "remaining"
                anchors.verticalCenter: parent.verticalCenter
                role: "label.medium"
                color: Theme.m3onSurfaceVariant
                font.features: ({tnum: 1})
                text: "−" + root.clock(root.player ? Math.max(0, root.player.duration - root.player.position) : 0)
            }
        }

        Item {
            width: parent.width
            height: Metrics.iconButtonSize + (Theme.spacing.small ?? 0)

            Row {
                id: left

                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacing.extraSmall ?? 0

                IconButton {
                    objectName: "muteButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.timed
                    icon: root.player && (root.player.muted || root.player.volume <= 0) ? "volume_off" : root.player && root.player.volume < 50 ? "volume_down" : "volume_up"
                    onClicked: root.player.toggleMute()

                    Tooltip {
                        text: (root.player && root.player.muted ? "Activar sonido" : "Silenciar") + " · M"
                    }
                }
                Slider {
                    objectName: "volumeSlider"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.timed && !root.compact
                    width: Metrics.iconButtonSize * 3
                    from: 0
                    to: 150
                    stepSize: 5
                    value: root.player ? (root.player.muted ? 0 : root.player.volume) : 0
                    onMoved: v => root.player.setVolume(v)

                    Tooltip {
                        text: "Volumen · ↑ ↓"
                    }
                }
            }

            Row {
                id: center

                anchors.centerIn: parent
                spacing: Theme.spacing.extraSmall ?? 0

                IconButton {
                    objectName: "previousButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.player !== null && root.player.count > 1
                    disabled: !root.player || !root.player.hasPrevious
                    icon: "skip_previous"
                    onClicked: root.player.stepCollection(-1)

                    Tooltip {
                        text: "Anterior · P"
                    }
                }
                IconButton {
                    objectName: "backButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.timed && !root.compact
                    icon: "replay_10"
                    onClicked: root.player.skip(-10)

                    Tooltip {
                        text: "Retroceder 10 s · ←"
                    }
                }
                // Circle while paused, rounded square while playing (the filled icon button's checked morph).
                IconButton {
                    objectName: "playButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.timed
                    type: "filled"
                    checkable: true
                    checked: root.playing
                    width: Metrics.iconButtonSize * 1.4
                    height: Metrics.iconButtonSize * 1.4
                    iconSize: Metrics.iconSize * 1.3
                    icon: "play_arrow"
                    iconChecked: "pause"
                    onClicked: {
                        checked = Qt.binding(() => root.playing);
                        root.player.toggle();
                    }

                    Tooltip {
                        text: (root.playing ? "Pausar" : "Reproducir") + " · Espacio"
                    }
                }
                IconButton {
                    objectName: "aheadButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.timed && !root.compact
                    icon: "forward_10"
                    onClicked: root.player.skip(10)

                    Tooltip {
                        text: "Avanzar 10 s · →"
                    }
                }
                IconButton {
                    objectName: "nextButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.player !== null && root.player.count > 1
                    disabled: !root.player || !root.player.hasNext
                    icon: "skip_next"
                    onClicked: root.player.stepCollection(1)

                    Tooltip {
                        text: "Siguiente · N"
                    }
                }
                IconButton {
                    objectName: "animationButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.kind === "image" && root.image !== null && root.image.animated
                    icon: root.image && root.image.playing ? "pause" : "play_arrow"
                    onClicked: root.image.toggleAnimation()

                    Tooltip {
                        text: "Reproducir o pausar la animación · Espacio"
                    }
                }
                IconButton {
                    objectName: "zoomOutButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.kind === "image"
                    icon: "zoom_out"
                    onClicked: root.image.zoomBy(1 / 1.25)

                    Tooltip {
                        text: "Alejar · −"
                    }
                }
                Button {
                    objectName: "zoomPill"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.kind === "image"
                    type: root.image && root.image.mode !== "fit" ? "tonal" : "text"
                    text: Math.round(root.image ? root.image.zoomPercent : 100) + " %"
                    onClicked: root.image.toggleFit()

                    Tooltip {
                        text: "Ajustar o tamaño real · 0 / 1"
                    }
                }
                IconButton {
                    objectName: "zoomInButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.kind === "image"
                    icon: "zoom_in"
                    onClicked: root.image.zoomBy(1.25)

                    Tooltip {
                        text: "Acercar · +"
                    }
                }
                IconButton {
                    objectName: "rotateButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.kind === "image" && !root.compact
                    icon: "rotate_right"
                    onClicked: root.image.rotate(1)

                    Tooltip {
                        text: "Girar · R"
                    }
                }
            }

            Row {
                id: right

                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacing.extraSmall ?? 0

                Button {
                    id: speed

                    objectName: "speedPill"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.timed && !root.compact
                    type: root.player && Math.abs(root.player.speed - 1) > 0.001 ? "tonal" : "text"
                    text: (root.player ? root.player.speed : 1) + "×"
                    onClicked: root.menuRequested("speed", speed)

                    Tooltip {
                        text: "Velocidad de reproducción · [ ]"
                    }
                }
                IconButton {
                    id: subtitles

                    objectName: "subtitlesButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.kind === "video" && !root.compact
                    icon: "closed_caption"
                    onClicked: root.menuRequested("subtitles", subtitles)

                    Tooltip {
                        text: "Subtítulos · C"
                    }
                }
                IconButton {
                    id: audio

                    objectName: "audioButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.timed && !root.compact && root.player !== null && root.player.audioTracks.length > 1
                    icon: "audiotrack"
                    onClicked: root.menuRequested("audio", audio)

                    Tooltip {
                        text: "Pista de audio · A"
                    }
                }
                IconButton {
                    id: more

                    objectName: "moreButton"
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "more_vert"
                    onClicked: root.menuRequested("more", more)

                    Tooltip {
                        text: "Más opciones"
                    }
                }
                IconButton {
                    objectName: "fullscreenButton"
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.kind !== "audio"
                    icon: root.player && root.player.fullscreen ? "fullscreen_exit" : "fullscreen"
                    onClicked: root.player.toggleFullscreen()

                    Tooltip {
                        text: root.player && root.player.fullscreen ? "Salir de pantalla completa · Esc" : "Pantalla completa · F"
                    }
                }
            }
        }
    }
}
