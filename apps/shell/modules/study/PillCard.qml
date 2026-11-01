pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// The pill unfolded on hover: the wavy ring large beside the block and phase, the session's blocks, and the
// controls.
Column {
    id: root

    required property var ui
    readonly property var s: Study.session
    readonly property bool focusing: Study.phase === "focus"
    readonly property int blocks: s?.blocks ?? 0

    signal stopRequested

    width: Tokens.padding.extraExtraLarge * 7
    padding: Tokens.padding.large
    spacing: Tokens.spacing.medium

    Row {
        spacing: Tokens.spacing.medium

        CircularProgress {
            anchors.verticalCenter: parent.verticalCenter
            implicitSize: Tokens.padding.extraExtraLarge - Tokens.padding.extraSmall
            strokeWidth: Tokens.padding.extraSmall
            value: Study.progress
            wavy: true
            waveAmplitude: 0.5
            wavePaused: Study.paused
            fgColour: root.focusing ? Colours.palette.m3primary : Colours.palette.m3tertiary
            bgColour: Qt.alpha(Colours.palette.m3onSurface, 0.1)
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter

            StyledText {
                text: !root.s ? "" : root.blocks ? `Bloque ${root.s.block} de ${root.blocks}` : `Bloque ${root.s.block}`
                font: Tokens.font.title.medium
            }

            StyledText {
                text: (Study.paused ? "En pausa" : root.focusing ? "Foco" : "Descanso")
                      + (root.ui.revealTime ? ` · quedan ${Study.remainingMin} min` : "")
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.medium
            }
        }
    }

    // One bar per block: done ones full, the current one tinted with its progress always visible.
    Row {
        visible: root.blocks > 0
        spacing: Tokens.spacing.extraSmall

        Repeater {
            model: root.blocks

            StyledRect {
                id: bar

                required property int index
                readonly property int n: index + 1
                readonly property bool done: n <= (root.s?.blocksDone ?? 0)
                readonly property bool current: n === root.s?.block && !done

                width: (root.width - root.padding * 2 - Tokens.spacing.extraSmall * (root.blocks - 1)) / root.blocks
                height: Tokens.padding.small + Tokens.padding.extraSmall / 2
                radius: height / 2
                color: done ? Colours.palette.m3primary
                    : current ? Qt.alpha(Colours.palette.m3primary, 0.22) : Qt.alpha(Colours.palette.m3onSurface, 0.1)

                StyledRect {
                    visible: bar.current && root.focusing
                    width: Math.max(bar.height, bar.width * Study.progress)
                    height: bar.height
                    radius: bar.radius
                    color: Colours.palette.m3primary

                    Behavior on width {
                        Anim {
                            type: Anim.StandardLarge
                        }
                    }
                }
            }
        }
    }

    Item {
        width: root.width - root.padding * 2
        implicitHeight: controls.implicitHeight

        Row {
            id: controls

            spacing: Tokens.spacing.small

            IconButton {
                icon: Study.paused ? "play_arrow" : "pause"
                type: IconButton.Filled
                onClicked: Study.togglePause()
            }

            IconButton {
                icon: "skip_next"
                type: IconButton.Tonal
                onClicked: Study.skipToBreak()
            }

            IconButton {
                icon: "stop"
                type: IconButton.Tonal
                onClicked: root.stopRequested()
            }
        }

        IconButton {
            anchors.right: parent.right
            anchors.verticalCenter: controls.verticalCenter
            icon: root.ui.revealTime ? "visibility_off" : "visibility"
            type: IconButton.Text
            onClicked: root.ui.revealTime = !root.ui.revealTime
        }
    }
}
