import QtQuick
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services

// The pill while studying: a wavy circular indicator that fills with the block, the phase and which
// block this is. Minutes only when asked for (hover, the eye button, or "hide time" turned off).
Row {
    id: root

    property bool showTime
    readonly property var s: Study.session
    readonly property bool focusing: Study.phase === "focus"

    leftPadding: Tokens.padding.small + Tokens.padding.extraSmall
    rightPadding: Tokens.padding.large
    spacing: Tokens.spacing.small + Tokens.spacing.extraSmall

    CircularProgress {
        anchors.verticalCenter: parent.verticalCenter
        implicitSize: Tokens.font.icon.medium.pointSize * 1.45
        strokeWidth: Tokens.padding.extraSmall / 2 + 1
        value: Study.progress
        wavy: true
        waveAmplitude: 0.6
        wavePaused: Study.paused
        fgColour: root.focusing ? Colours.palette.m3primary : Colours.palette.m3tertiary
        bgColour: Qt.alpha(Colours.palette.m3onSurface, 0.12)
    }

    StyledText {
        anchors.verticalCenter: parent.verticalCenter
        text: Study.paused ? "Pausa" : root.focusing ? "Foco" : "Descanso"
        font: Tokens.font.label.large
    }

    StyledText {
        anchors.verticalCenter: parent.verticalCenter
        text: !root.s ? "" : root.s.blocks ? `${root.s.block} de ${root.s.blocks}` : `Bloque ${root.s.block}`
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.label.large
    }

    StyledText {
        anchors.verticalCenter: parent.verticalCenter
        visible: root.showTime
        text: `· ${Study.remainingMin} min`
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.label.large
    }
}
