// «Ahora suena»: covers the window. Left: the cover big in a turning cookie (circle while paused), title, artist
// (link), album and quality, the wavy position, large transport and volume. Right (below on narrow windows):
// Letra / A continuación. Opened on «now» the tab follows the lyrics — a song without them shows the queue with a
// note — while a tab the user chose stays. Esc or the chevron closes it.
import QtQuick
import QtQuick.Effects
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

    // The artwork as the room the record player stands in.
    AmbientBackdrop {
        anchors.fill: parent
        source: player.coverUrl
        tone: player.tone !== "" ? player.tone : Theme.m3primaryContainer
        fadeBottom: false
    }

    // Nothing reaches the page behind: clicks, the wheel and hover stop here.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        hoverEnabled: true
        onWheel: wheel => wheel.accepted = true
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
        // The record player takes whatever height the song's details leave, so the column is always full.
        Item {
            id: left

            x: Theme.padding.extraLarge ?? 0
            width: root.wide ? parent.width * 0.44 : parent.width - 2 * x
            height: root.wide ? parent.height - (Theme.padding.large ?? 0) : Math.min(width / 1.55, content.height * 0.3) + details.height + details.anchors.topMargin

            Turntable {
                id: art

                objectName: "turntable"
                readonly property real room: root.wide ? left.height - details.height - (Theme.spacing.large ?? 0) : content.height * 0.3
                anchors.horizontalCenter: parent.horizontalCenter
                y: root.wide ? Math.max(0, (room - height) / 2) : 0
                width: Math.min(left.width, room * 1.55)
                height: width / 1.55
                cover: player.coverUrl
                trackKey: player.currentKey
                playing: player.playing
                progress: player.duration > 0 ? clock.position / player.duration : 0
                tone: player.tone !== "" ? player.tone : Theme.m3primaryContainer
            }

            Column {
                id: details

                anchors.bottom: root.wide ? parent.bottom : undefined
                anchors.top: root.wide ? undefined : art.bottom
                anchors.topMargin: root.wide ? 0 : Theme.spacing.medium ?? 0
                width: parent.width
                spacing: Theme.spacing.medium ?? 0

                Item {
                    id: titleBlock

                    width: parent.width
                    height: titles.implicitHeight

                    // A new song's name rises into place.
                    property real shift: 0
                    opacity: 1 - shift
                    transform: Translate {
                        y: titleBlock.shift * (Theme.spacing.extraLarge ?? 0)
                    }
                    Connections {
                        target: player
                        function onCurrentKeyChanged() {
                            if (!Motion.reduced)
                                titleIn.restart();
                        }
                    }
                    SequentialAnimation {
                        id: titleIn

                        PropertyAction {
                            target: titleBlock
                            property: "shift"
                            value: 1
                        }
                        PauseAnimation {
                            duration: Theme.duration("normal")
                        }
                        Anim {
                            target: titleBlock
                            property: "shift"
                            to: 0
                            kind: "slowSpatial"
                        }
                    }

                    Column {
                        id: titles

                        width: parent.width - heart.width - (Theme.spacing.small ?? 0)
                        spacing: Theme.spacing.extraSmall ?? 0

                        // The song's name, big; a name too long for the column glides across it.
                        Item {
                            id: titleClip

                            width: parent.width
                            height: titleLabel.implicitHeight
                            clip: titleLabel.overflow > 0
                            // While it glides the name melts into the edges instead of being cut.
                            layer.enabled: titleLabel.overflow > 0 && GraphicsInfo.api !== GraphicsInfo.Software
                            layer.effect: MultiEffect {
                                maskEnabled: true
                                maskSource: titleFade
                                maskThresholdMin: 0.5
                                maskSpreadAtMin: 1.0
                            }

                            Rectangle {
                                id: titleFade

                                anchors.fill: parent
                                visible: false
                                layer.enabled: true
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop {
                                        position: 0
                                        color: "transparent"
                                    }
                                    GradientStop {
                                        position: 0.04
                                        color: Theme.m3onSurface
                                    }
                                    GradientStop {
                                        position: 0.92
                                        color: Theme.m3onSurface
                                    }
                                    GradientStop {
                                        position: 1
                                        color: "transparent"
                                    }
                                }
                            }

                            Label {
                                id: titleLabel

                                objectName: "nowTitle"
                                readonly property real overflow: Math.max(0, implicitWidth - titleClip.width)
                                role: "headline.large"
                                font.pointSize: Theme.typeFont("headline.large").pointSize * (root.wide ? 1.55 : 1.1)
                                font.weight: Font.DemiBold
                                text: player.currentKey === "" ? "Nada sonando" : player.title

                                SequentialAnimation on x {
                                    running: titleLabel.overflow > 0 && root.open && !Motion.reduced
                                    loops: Animation.Infinite
                                    onRunningChanged: if (!running) titleLabel.x = 0

                                    PauseAnimation {
                                        duration: Theme.duration("extraLarge") * 2.5
                                    }
                                    NumberAnimation {
                                        to: -titleLabel.overflow
                                        duration: titleLabel.overflow * 28
                                        easing.type: Easing.InOutSine
                                    }
                                    PauseAnimation {
                                        duration: Theme.duration("extraLarge") * 1.5
                                    }
                                    NumberAnimation {
                                        to: 0
                                        duration: titleLabel.overflow * 12
                                        easing.type: Easing.InOutSine
                                    }
                                }
                            }
                        }
                        Label {
                            width: Math.min(implicitWidth, parent.width)
                            role: "title.large"
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
                            visible: text !== ""
                            role: "title.small"
                            text: [player.album, player.quality].filter(t => t !== "").join("  ·  ")
                            color: Qt.tint(Theme.m3onSurfaceVariant, Qt.alpha(player.tone !== "" ? player.tone : Theme.m3primary, 0.35))
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
                        value: clock.position
                        stepSize: 5
                        pageStep: 30
                        live: false
                        wavy: true
                        waveMoving: player.playing
                        disabled: player.currentKey === ""
                        onMoved: v => player.seek(v)

                        Binding on value {
                            value: clock.position
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
                        // The record's colour on the main button (artwork-derived tone, readable on either mode).
                        containerColor: player.tone !== "" ? Qt.tint(Theme.m3primaryContainer, Qt.alpha(player.tone, 0.55)) : Theme.m3primaryContainer
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
                glow: player.tone !== "" ? Qt.tint(Theme.m3primary, Qt.alpha(player.tone, 0.45)) : Theme.m3primary
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

    // Smooth position for the bars and the record.
    PlayClock {
        id: clock
    }
}
