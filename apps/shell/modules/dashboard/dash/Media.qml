pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Components
import Wysun.Config
import Wysun.I18n
import Wysun.Services
import qs.components
import qs.components.controls
import qs.components.widgets
import qs.services
import qs.utils

// The dashboard's media card as a little stage: the waffle dances under a spotlight (at the music's
// tempo), and a compact strip below holds the cover, the track, a wavy progress bar and the controls.
Item {
    id: root

    property real playerProgress: {
        const active = Players.active;
        return active?.length ? (active.position % active.length) / active.length : 0;
    }

    readonly property bool playing: Players.active?.isPlaying ?? false

    anchors.top: parent.top
    anchors.bottom: parent.bottom
    implicitWidth: Tokens.sizes.dashboard.mediaWidth * 1.6

    Behavior on playerProgress {
        Anim {
            type: Anim.StandardLarge
        }
    }

    Timer {
        running: root.playing
        interval: GlobalConfig.dashboard.mediaUpdateInterval
        triggeredOnStart: true
        repeat: true
        onTriggered: Players.active?.positionChanged()
    }

    ServiceRef {
        service: Audio.beatTracker
    }

    // ------------------------------------------------ the stage
    Item {
        id: stage

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: strip.top
        anchors.margins: Tokens.padding.large
        anchors.bottomMargin: Tokens.spacing.small

        // The spotlight: a soft disc that breathes while music plays.
        StyledRect {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: floor.top
            anchors.bottomMargin: -height * 0.12
            width: Math.min(parent.width, parent.height) * 0.92
            height: width
            radius: width / 2
            color: Qt.alpha(Colours.palette.m3primary, root.playing ? 0.1 : 0.05)
            scale: root.playing ? 1 + 0.03 * Math.sin(beat.phase * Math.PI * 2) : 1

            Behavior on color {
                CAnim {}
            }
        }

        // The floor it dances on.
        StyledRect {
            id: floor

            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            width: parent.width * 0.62
            height: Tokens.padding.small
            radius: height / 2
            color: Qt.alpha(Colours.palette.m3primary, 0.18)
        }

        Waffle {
            anchors.top: parent.top
            anchors.bottom: floor.verticalCenter
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width

            act: "dance"
            playing: root.playing
            bpm: Audio.beatTracker.bpm
        }

        // Drives the spotlight's breathing at the music's tempo.
        NumberAnimation {
            id: beat

            property real phase: 0
            target: beat
            property: "phase"
            from: 0
            to: 1
            loops: Animation.Infinite
            running: root.playing
            duration: Math.max(250, 60000 / Math.max(1, Audio.beatTracker.bpm))
        }
    }

    // ------------------------------------------------ the strip
    StyledRect {
        id: strip

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Tokens.padding.medium
        implicitHeight: content.implicitHeight + Tokens.padding.large * 2
        radius: Tokens.rounding.large
        color: Colours.layer(Colours.palette.m3surfaceContainerHigh, 2)

        Column {
            id: content

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Tokens.padding.large
            spacing: Tokens.spacing.medium

            Row {
                width: parent.width
                spacing: Tokens.spacing.medium

                CoverArt {
                    id: cover
                    width: Tokens.sizes.dashboard.mediaWidth * 0.3
                    height: width
                }

                Column {
                    anchors.verticalCenter: cover.verticalCenter
                    width: parent.width - cover.width - parent.spacing
                    spacing: Tokens.spacing.extraSmall

                    StyledText {
                        width: parent.width
                        animate: true
                        text: (Players.active?.trackTitle ?? Tr.tr("No media")) || Tr.tr("Unknown title")
                        color: Colours.palette.m3primary
                        font: Tokens.font.title.small
                        elide: Text.ElideRight
                    }

                    StyledText {
                        width: parent.width
                        animate: true
                        text: (Players.active?.trackArtist ?? Tr.tr("No media")) || Tr.tr("Unknown artist")
                        color: Colours.palette.m3secondary
                        font: Tokens.font.body.small
                        elide: Text.ElideRight
                    }
                }
            }

            StyledProgressBar {
                width: parent.width
                implicitHeight: Tokens.padding.small
                value: root.playerProgress
                wavy: true
                wavePaused: !root.playing
                waveFrequency: 8
                waveDuration: 2000
            }

            ButtonRow {
                width: parent.width
                spacing: Tokens.spacing.extraSmall

                IconButton {
                    type: IconButton.Tonal
                    icon: "skip_previous"
                    isRound: true
                    shapeMorph: true
                    disabled: !Players.active?.canGoPrevious
                    onClicked: Players.active?.previous()
                }

                IconButton {
                    fillWidth: true
                    icon: root.playing ? "pause" : "play_arrow"
                    isRound: true
                    shapeMorph: true
                    checked: root.playing
                    disabled: !Players.active?.canTogglePlaying
                    onClicked: Players.active?.togglePlaying()
                }

                IconButton {
                    type: IconButton.Tonal
                    icon: "skip_next"
                    isRound: true
                    shapeMorph: true
                    disabled: !Players.active?.canGoNext
                    onClicked: Players.active?.next()
                }
            }
        }
    }
}
