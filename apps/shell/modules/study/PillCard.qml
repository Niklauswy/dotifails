pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// The pill unfolded on hover: block, phase, the session's blocks and the controls.
Column {
    id: root

    required property var ui
    readonly property var s: Study.session

    signal stopRequested

    width: Tokens.padding.extraExtraLarge * 7
    padding: Tokens.padding.large
    spacing: Tokens.spacing.small

    StyledText {
        text: !root.s ? "" : root.s.blocks ? `Bloque ${root.s.block} de ${root.s.blocks}` : `Bloque ${root.s.block}`
        font: Tokens.font.title.medium
    }

    Row {
        spacing: Tokens.spacing.small

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: Tokens.padding.small
            height: width
            radius: width / 2
            color: Study.phase === "focus" ? Colours.palette.m3primary : Colours.palette.m3tertiary
            opacity: Study.paused ? 0.4 : 1
        }

        StyledText {
            text: (Study.paused ? "En pausa" : Study.phase === "focus" ? "Foco" : "Descanso")
                  + (root.ui.revealTime ? ` · quedan ${Study.remainingMin} min` : "")
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.body.small
        }
    }

    Row {
        visible: !!root.s?.blocks
        topPadding: Tokens.spacing.small
        bottomPadding: Tokens.spacing.small
        spacing: Tokens.spacing.extraSmall + 2

        Repeater {
            model: root.s?.blocks ?? 0

            StyledRect {
                required property int index
                readonly property int n: index + 1

                width: (root.width - root.padding * 2 - parent.spacing * ((root.s?.blocks ?? 1) - 1)) / (root.s?.blocks ?? 1)
                height: Tokens.padding.small
                radius: height / 2
                color: Qt.alpha(Colours.palette.m3onSurface, 0.12)
                clip: true

                Rectangle {
                    height: parent.height
                    radius: parent.radius
                    color: Colours.palette.m3primary
                    width: parent.width * (parent.n <= (root.s?.blocksDone ?? 0) ? 1
                                           : parent.n === root.s?.block && Study.phase === "focus" ? Study.progress : 0)
                }
            }
        }
    }

    Row {
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

        Item {
            width: root.width - root.padding * 2 - parent.spacing * 4 - eye.width * 4
            height: 1
        }

        IconButton {
            id: eye

            icon: root.ui.revealTime ? "visibility_off" : "visibility"
            type: IconButton.Text
            onClicked: root.ui.revealTime = !root.ui.revealTime
        }
    }
}
