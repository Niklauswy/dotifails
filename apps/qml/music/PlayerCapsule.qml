// The player capsule at the bottom of the window: cover (opens «Ahora suena»), title and artist (link), favourite,
// shuffle / previous / play-pause / next / repeat with the wavy position, and lyrics / queue / mute / volume.
// Narrow windows keep the cover, the titles, play and next, and a thin progress line.
import QtQuick
import WysunM3
import "parts"

Item {
    id: root

    property var app
    readonly property bool compact: width < Metrics.windowMedium
    // The capsule sits beside the drawer: its own width decides how much it shows.
    readonly property bool wide: width >= Metrics.windowExpanded - Metrics.railWidth
    readonly property bool empty: player.currentKey === ""

    signal panelRequested(string tab)

    implicitHeight: (compact ? Metrics.listItemOneLine + Metrics.progressThickness : Metrics.topAppBarMedium - Metrics.textFieldFocusWidth * 4) + 2 * (Theme.padding.small ?? 0)
    height: implicitHeight

    Surface {
        id: capsule

        objectName: "playerCapsule"
        anchors.fill: parent
        anchors.margins: Theme.padding.small ?? 0
        radius: Theme.rounding.extraLarge ?? 0
        container: Theme.m3surfaceContainerHigh
        color: container
        level: 1
        clip: true

        // ---------------------------------------------------------------- now
        Item {
            id: now

            x: Theme.padding.medium ?? 0
            width: root.compact ? parent.width - x - controlsCompact.width - (Theme.padding.small ?? 0) : Math.min(parent.width * 0.3, Metrics.textFieldMinWidth * 1.6)
            height: root.compact ? parent.height - Metrics.progressThickness : parent.height

            Cover {
                id: cover

                objectName: "capsuleCover"
                anchors.verticalCenter: parent.verticalCenter
                width: root.compact ? Metrics.listAvatarSize + Metrics.chipIconSize / 2 : Metrics.listImageSize
                height: width
                source: player.coverUrl
                shape: player.playing ? "cookie12" : "circle"
                spinning: player.playing
                placeholderIcon: "music_note"

                StateLayer {
                    radius: cover.width / 2
                    disabled: root.empty
                    onClicked: root.panelRequested("now")
                }

                Tooltip {
                    text: "Abrir Ahora suena · Ctrl+P"
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                x: cover.width + (Theme.spacing.medium ?? 0)
                width: parent.width - x - (heart.visible ? heart.width : 0)

                Label {
                    objectName: "capsuleTitle"
                    width: parent.width
                    role: "title.small"
                    text: root.empty ? "Nada sonando" : player.title
                    elide: Text.ElideRight
                }
                Label {
                    id: artistLink

                    width: Math.min(implicitWidth, parent.width)
                    role: "body.small"
                    text: root.empty ? "Elige una canción" : player.artist
                    color: linkArea.containsMouse ? Theme.m3primary : Theme.m3onSurfaceVariant
                    font.underline: linkArea.containsMouse
                    elide: Text.ElideRight

                    MouseArea {
                        id: linkArea

                        anchors.fill: parent
                        enabled: player.artists.length > 0
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.app.navigate("collection:artist:" + player.artists[0], true)
                    }
                }
            }

            IconButton {
                id: heart

                objectName: "capsuleFavorite"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                visible: !root.empty && !root.compact
                checkable: true
                checked: player.favorite
                icon: "favorite"
                iconChecked: "favorite"
                onClicked: player.toggleFavorite()

                Tooltip {
                    text: "Guardar en Tus me gusta · Ctrl+Mayús+F"
                }
            }
        }

        // ---------------------------------------------------------- transport
        Column {
            visible: !root.compact
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(parent.width * 0.4, Metrics.textFieldMinWidth * 2.4)
            spacing: 0

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Theme.spacing.small ?? 0

                IconButton {
                    objectName: "shuffleButton"
                    anchors.verticalCenter: parent.verticalCenter
                    checkable: true
                    checked: player.shuffle
                    icon: "shuffle"
                    onClicked: player.setShuffle(!player.shuffle)

                    Tooltip {
                        text: "Aleatorio · Ctrl+S"
                    }
                }
                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "skip_previous"
                    disabled: !player.canPrevious
                    onClicked: player.previous()

                    Tooltip {
                        text: "Anterior · Ctrl+←"
                    }
                }
                PlayButton {
                    objectName: "playButton"
                    anchors.verticalCenter: parent.verticalCenter
                }
                IconButton {
                    objectName: "nextButton"
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "skip_next"
                    disabled: !player.canNext
                    onClicked: player.next()

                    Tooltip {
                        text: "Siguiente · Ctrl+→"
                    }
                }
                IconButton {
                    objectName: "repeatButton"
                    anchors.verticalCenter: parent.verticalCenter
                    checkable: true
                    checked: player.repeat !== "off"
                    icon: player.repeat === "one" ? "repeat_one" : "repeat"
                    iconChecked: icon
                    onClicked: player.cycleRepeat()

                    Tooltip {
                        text: player.repeatLabel + " · Ctrl+R"
                    }
                }
            }

            Row {
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    role: "label.small"
                    text: progress.pressed ? Format.clock(progress.value) : player.positionText
                    color: Theme.m3onSurfaceVariant
                }
                Slider {
                    id: progress

                    objectName: "positionSlider"
                    width: parent.width - 2 * (Metrics.listAvatarSize + parent.spacing)
                    from: 0
                    to: Math.max(1, player.duration)
                    value: player.position
                    stepSize: 5
                    pageStep: 30
                    live: false
                    wavy: true
                    waveMoving: player.playing
                    disabled: root.empty
                    onMoved: v => player.seek(v)

                    // Follow the player except while the user drags (a drag or a key press writes `value`).
                    Binding on value {
                        value: player.position
                        when: !progress.pressed
                        restoreMode: Binding.RestoreNone
                    }
                }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    role: "label.small"
                    text: player.durationText
                    color: Theme.m3onSurfaceVariant
                }
            }
        }

        // -------------------------------------------------------------- tools
        Row {
            visible: !root.compact
            anchors.right: parent.right
            anchors.rightMargin: Theme.padding.medium ?? 0
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spacing.extraSmall ?? 0

            IconButton {
                objectName: "lyricsButton"
                anchors.verticalCenter: parent.verticalCenter
                icon: "lyrics"
                disabled: root.empty
                onClicked: root.panelRequested("lyrics")

                Tooltip {
                    text: "Letra · Ctrl+L"
                }
            }
            IconButton {
                objectName: "queueButton"
                anchors.verticalCenter: parent.verticalCenter
                icon: "queue_music"
                onClicked: root.panelRequested("queue")

                Tooltip {
                    text: "Cola · Ctrl+Q"
                }
            }
            IconButton {
                objectName: "muteButton"
                anchors.verticalCenter: parent.verticalCenter
                icon: player.volumeIcon
                onClicked: player.toggleMute()

                Tooltip {
                    text: "Silenciar · M"
                }
            }
            Slider {
                id: volumeSlider

                objectName: "volumeSlider"
                visible: root.wide
                anchors.verticalCenter: parent.verticalCenter
                width: Metrics.textFieldMinWidth * 0.5
                from: 0
                to: 100
                stepSize: 5
                value: player.muted ? 0 : player.volume
                onMoved: v => player.setVolume(Math.round(v))

                Binding on value {
                    value: player.muted ? 0 : player.volume
                    when: !volumeSlider.pressed
                    restoreMode: Binding.RestoreNone
                }
            }
        }

        // ------------------------------------------------------------ compact
        Row {
            id: controlsCompact

            visible: root.compact
            anchors.right: parent.right
            anchors.rightMargin: Theme.padding.small ?? 0
            y: (parent.height - Metrics.progressThickness - height) / 2
            spacing: Theme.spacing.extraSmall ?? 0

            PlayButton {
                anchors.verticalCenter: parent.verticalCenter
            }
            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                icon: "skip_next"
                disabled: !player.canNext
                onClicked: player.next()
            }
        }

        LinearProgress {
            visible: root.compact
            anchors.bottom: parent.bottom
            width: parent.width
            value: player.duration > 0 ? player.position / player.duration : 0
        }
    }

    // Play / pause: a circle that turns into a rounded square while music plays (M3 Expressive shape change).
    component PlayButton: IconButton {
        type: "filled"
        icon: player.playing ? "pause" : "play_arrow"
        restRadius: player.playing ? Theme.rounding.medium ?? 0 : Theme.fullRadius(height)
        onClicked: player.toggle()

        Tooltip {
            text: player.playing ? "Pausar · Espacio" : "Reproducir · Espacio"
        }
    }
}
