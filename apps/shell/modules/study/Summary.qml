pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.services

// End of a session: blocks, time studied, distractions held back and this week's minutes per day.
Column {
    id: root

    readonly property var r: Study.lastSummary
    readonly property var week: Study.week
    readonly property int today: (new Date().getDay() + 6) % 7
    readonly property int peak: Math.max(1, ...week)

    signal again
    signal closeRequested

    function formatMinutes(m: int): string {
        if (m < 60)
            return `${m} min`;
        return m % 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m / 60} h`;
    }

    function dateLine(): string {
        const text = Qt.locale("es_ES").toString(new Date(), "dddd d 'de' MMMM");
        return text.charAt(0).toUpperCase() + text.slice(1);
    }

    width: Tokens.padding.extraExtraLarge * 9
    padding: Tokens.padding.extraLarge - Tokens.padding.extraSmall
    spacing: 0

    StyledText {
        text: "Sesión terminada"
        font: Tokens.font.headline.small
    }

    StyledText {
        topPadding: Tokens.spacing.extraSmall
        text: root.dateLine()
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.medium
    }

    Row {
        topPadding: Tokens.spacing.large + Tokens.spacing.extraSmall
        bottomPadding: Tokens.spacing.large + Tokens.spacing.extraSmall
        spacing: Tokens.spacing.small + 2

        Repeater {
            model: !root.r ? [] : [
                {value: root.r.blocksPlanned ? `${root.r.blocksDone} / ${root.r.blocksPlanned}` : `${root.r.blocksDone}`, label: "bloques de foco"},
                {value: root.formatMinutes(root.r.focusMin), label: "estudiando"},
                {value: `${root.r.distractions}`, label: "distracciones frenadas"}
            ]

            StyledRect {
                id: stat

                required property var modelData

                width: (root.width - root.padding * 2 - Tokens.spacing.small * 2 - 4) / 3
                implicitHeight: statCol.implicitHeight
                radius: Tokens.rounding.large
                color: Colours.palette.m3surfaceContainerHigh

                Column {
                    id: statCol

                    width: parent.width
                    padding: Tokens.padding.medium + 2

                    StyledText {
                        text: stat.modelData.value
                        font: Tokens.font.headline.small
                    }

                    StyledText {
                        width: parent.width - parent.padding * 2
                        wrapMode: Text.WordWrap
                        text: stat.modelData.label
                        color: Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.label.medium
                    }
                }
            }
        }
    }

    StyledText {
        bottomPadding: Tokens.spacing.small
        text: "Esta semana"
        font: Tokens.font.title.small
    }

    Row {
        spacing: Tokens.spacing.small

        Repeater {
            model: ["L", "M", "X", "J", "V", "S", "D"]

            Column {
                id: day

                required property string modelData
                required property int index

                spacing: Tokens.spacing.extraSmall + 2

                Item {
                    width: (root.width - root.padding * 2 - Tokens.spacing.small * 6) / 7
                    height: Tokens.padding.extraLarge + Tokens.padding.large

                    StyledRect {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: Math.max(Tokens.padding.extraSmall - 1, parent.height * root.week[day.index] / root.peak)
                        radius: Tokens.rounding.small
                        color: day.index === root.today ? Colours.palette.m3primary : Colours.palette.m3secondaryContainer
                        opacity: root.week[day.index] > 0 || day.index === root.today ? 1 : 0.4
                    }
                }

                StyledText {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: day.modelData
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.label.small
                }
            }
        }
    }

    Item {
        width: root.width - root.padding * 2
        implicitHeight: closeButton.implicitHeight + Tokens.spacing.extraLarge - Tokens.spacing.extraSmall

        ActionButton {
            anchors.bottom: parent.bottom
            kind: "text"
            text: "Otra sesión"
            onClicked: root.again()
        }

        ActionButton {
            id: closeButton

            anchors.right: parent.right
            anchors.bottom: parent.bottom
            text: "Cerrar"
            onClicked: root.closeRequested()
        }
    }
}
