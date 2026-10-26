// «Ahora suena»: covers the window. Left: the cover big in a turning cookie (circle while paused), title, artist
// (link), album and quality, the wavy position, large transport and volume. Right (below on narrow windows):
// Letra / A continuación. Opened on «now» the tab follows the lyrics — a song without them shows the queue with a
// note — while a tab the user chose stays. Esc or the chevron closes it.
import QtQuick
import WysunM3
import "parts"

FocusScope {
    id: root

    property var app
    property bool open
    property string tab: "lyrics"          // lyrics | queue
    property bool chosen                   // the user picked the tab: never switch it for them
    readonly property bool autoQueue: !chosen && tab === "lyrics" && (lyrics.state === "missing" || lyrics.state === "instrumental")
    readonly property string shownTab: autoQueue ? "queue" : tab
    readonly property bool wide: width >= Metrics.windowExpanded

    signal closeRequested

    objectName: "nowPlaying"
    visible: opacity > 0
    opacity: open ? 1 : 0
    enabled: open

    SpringBehavior on opacity {
        kind: "defaultEffects"
    }

    Keys.onEscapePressed: closeRequested()

    Rectangle {
        anchors.fill: parent
        color: Theme.m3surfaceContainerLow
    }

    // A soft disc of the primary container behind the cover, breathing while music plays.
    Rectangle {
        x: left.x + art.x + art.width / 2 - width / 2
        y: content.y + left.y + art.y + art.height / 2 - height / 2
        width: art.width * 1.15
        height: width
        radius: width / 2
        color: Theme.m3primaryContainer
        opacity: 0.35
        scale: breathe.value

        QtObject {
            id: breathe

            property real value: 1
        }
        SequentialAnimation {
            running: player.playing && root.open && !Motion.reduced
            loops: Animation.Infinite

            NumberAnimation {
                target: breathe
                property: "value"
                to: 1.06
                duration: Theme.duration("extraLarge") * 2
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Motion.bezier("emphasized")
            }
            NumberAnimation {
                target: breathe
                property: "value"
                to: 1
                duration: Theme.duration("extraLarge") * 2
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Motion.bezier("emphasized")
            }
        }
    }

    Item {
        id: topLine

        width: parent.width
        height: Metrics.topAppBarSmall

        IconButton {
            objectName: "closeNowPlaying"
            x: Theme.padding.medium ?? 0
            anchors.verticalCenter: parent.verticalCenter
            type: "tonal"
            icon: "expand_more"
            onClicked: root.closeRequested()

            Tooltip {
                text: "Cerrar · Esc"
            }
        }
        Label {
            anchors.centerIn: parent
            role: "label.large"
            text: ("Ahora suena" + (player.contextTitle !== "" ? " · " + player.contextTitle.slice(3) : "")).toUpperCase()
            color: Theme.m3onSurfaceVariant
        }
    }

    Item {
        id: content

        y: topLine.height
        width: parent.width
        height: parent.height - y

        // ---------------------------------------------------------------- player
        Column {
            id: left

            x: Theme.padding.extraLarge ?? 0
            width: root.wide ? parent.width * 0.42 : parent.width - 2 * x
            spacing: Theme.spacing.medium ?? 0

            Cover {
                id: art

                objectName: "nowCover"
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(MusicMetrics.nowPlayingCover, left.width * 0.8, root.wide ? content.height * 0.5 : content.height * 0.28)
                height: width
                source: player.coverUrl
                shape: player.playing ? "cookie12" : "circle"
                spinning: player.playing
            }

            Item {
                width: parent.width
                height: titles.implicitHeight

                Column {
                    id: titles

                    width: parent.width - heart.width

                    Label {
                        objectName: "nowTitle"
                        width: parent.width
                        role: "headline.medium"
                        text: player.currentKey === "" ? "Nada sonando" : player.title
                        elide: Text.ElideRight
                    }
                    Label {
                        width: Math.min(implicitWidth, parent.width)
                        role: "title.medium"
                        text: player.currentKey === "" ? "Elige una canción de tu biblioteca" : player.artist
                        color: artistArea.containsMouse ? Theme.m3primary : Theme.m3onSurfaceVariant
                        font.underline: artistArea.containsMouse
                        elide: Text.ElideRight

                        MouseArea {
                            id: artistArea

                            anchors.fill: parent
                            enabled: player.artists.length > 0
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.closeRequested();
                                root.app.navigate("collection:artist:" + player.artists[0], true);
                            }
                        }
                    }
                    Label {
                        width: parent.width
                        role: "body.medium"
                        text: [player.album, player.quality].filter(t => t !== "").join(" · ")
                        color: Theme.m3onSurfaceVariant
                        elide: Text.ElideRight
                    }
                }
                IconButton {
                    id: heart

                    anchors.right: parent.right
                    anchors.verticalCenter: titles.verticalCenter
                    type: "tonal"
                    checkable: true
                    checked: player.favorite
                    disabled: player.currentKey === ""
                    icon: "favorite"
                    iconChecked: "favorite"
                    onClicked: player.toggleFavorite()
                }
            }

            Row {
                width: parent.width
                spacing: Theme.spacing.small ?? 0

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    role: "label.medium"
                    text: progress.pressed ? Format.clock(progress.value) : player.positionText
                    color: Theme.m3onSurfaceVariant
                }
                Slider {
                    id: progress

                    objectName: "nowPosition"
                    width: parent.width - 2 * (Metrics.listAvatarSize + parent.spacing)
                    from: 0
                    to: Math.max(1, player.duration)
                    value: player.position
                    stepSize: 5
                    pageStep: 30
                    live: false
                    wavy: true
                    waveMoving: player.playing
                    disabled: player.currentKey === ""
                    onMoved: v => player.seek(v)

                    Binding on value {
                        value: player.position
                        when: !progress.pressed
                        restoreMode: Binding.RestoreNone
                    }
                }
                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    role: "label.medium"
                    text: player.durationText
                    color: Theme.m3onSurfaceVariant
                }
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Theme.spacing.large ?? 0

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    checkable: true
                    checked: player.shuffle
                    icon: "shuffle"
                    onClicked: player.setShuffle(!player.shuffle)
                }
                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    type: "tonal"
                    icon: "skip_previous"
                    disabled: !player.canPrevious
                    onClicked: player.previous()
                }
                Fab {
                    objectName: "nowPlay"
                    anchors.verticalCenter: parent.verticalCenter
                    size: "large"
                    icon: player.playing ? "pause" : "play_arrow"
                    restRadius: player.playing ? Theme.rounding.large ?? 0 : Theme.fullRadius(height)
                    onClicked: player.toggle()
                }
                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    type: "tonal"
                    icon: "skip_next"
                    disabled: !player.canNext
                    onClicked: player.next()
                }
                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    checkable: true
                    checked: player.repeat !== "off"
                    icon: player.repeat === "one" ? "repeat_one" : "repeat"
                    iconChecked: icon
                    onClicked: player.cycleRepeat()
                }
            }

            Row {
                visible: root.wide
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Theme.spacing.small ?? 0

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: player.volumeIcon
                    onClicked: player.toggleMute()
                }
                Slider {
                    id: volume

                    anchors.verticalCenter: parent.verticalCenter
                    width: left.width * 0.5
                    from: 0
                    to: 100
                    stepSize: 5
                    value: player.muted ? 0 : player.volume
                    onMoved: v => player.setVolume(Math.round(v))

                    Binding on value {
                        value: player.muted ? 0 : player.volume
                        when: !volume.pressed
                        restoreMode: Binding.RestoreNone
                    }
                }
            }
        }

        // ----------------------------------------------------------- lyrics/queue
        Item {
            id: right

            x: root.wide ? left.x + left.width + (Theme.spacing.extraLarge ?? 0) * 1.5 : Theme.padding.extraLarge ?? 0
            y: root.wide ? 0 : left.height + (Theme.spacing.large ?? 0)
            width: root.wide ? parent.width - x - (Theme.padding.extraLarge ?? 0) : parent.width - 2 * x
            height: parent.height - y - (Theme.padding.large ?? 0)

            SegmentedButtons {
                id: tabs

                objectName: "nowTabs"
                model: [{value: "lyrics", text: "Letra", icon: "lyrics"}, {value: "queue", text: "A continuación", icon: "queue_music"}]
                current: root.shownTab
                onActivated: value => {
                    root.tab = value;
                    root.chosen = true;
                }
            }

            LyricsView {
                id: lyricsView

                objectName: "lyricsView"
                visible: root.shownTab === "lyrics"
                y: tabs.height + (Theme.spacing.medium ?? 0)
                width: parent.width
                height: parent.height - y - footer.height
                focus: visible
            }

            Row {
                id: footer

                visible: root.shownTab === "lyrics" && lyrics.state === "synced"
                anchors.bottom: parent.bottom
                width: parent.width
                height: visible ? Metrics.buttonHeight : 0
                spacing: Theme.spacing.small ?? 0

                Label {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - x - offsetControls.width
                    role: "label.medium"
                    text: lyrics.source
                    color: Theme.m3onSurfaceVariant
                }
                Row {
                    id: offsetControls

                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.spacing.extraSmall ?? 0

                    Label {
                        anchors.verticalCenter: parent.verticalCenter
                        role: "label.medium"
                        text: "Desfase"
                        color: Theme.m3onSurfaceVariant
                    }
                    IconButton {
                        objectName: "lyricsEarlier"
                        type: "tonal"
                        icon: "remove"
                        onClicked: lyrics.nudge(-0.5)

                        Tooltip {
                            text: "Adelantar la letra 0,5 s"
                        }
                    }
                    Label {
                        objectName: "lyricsOffset"
                        anchors.verticalCenter: parent.verticalCenter
                        width: Metrics.listAvatarSize * 1.2
                        role: "label.large"
                        text: lyrics.offsetText
                        horizontalAlignment: Text.AlignHCenter
                    }
                    IconButton {
                        objectName: "lyricsLater"
                        type: "tonal"
                        icon: "add"
                        onClicked: lyrics.nudge(0.5)

                        Tooltip {
                            text: "Retrasar la letra 0,5 s"
                        }
                    }
                }
            }

            QueueList {
                objectName: "queueView"
                visible: root.shownTab === "queue"
                y: tabs.height + (Theme.spacing.medium ?? 0)
                width: parent.width
                height: parent.height - y
                app: root.app
                note: root.autoQueue ? lyrics.message : ""
            }
        }
    }
}
