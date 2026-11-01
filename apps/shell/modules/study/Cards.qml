pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Wysun.Config
import qs.components
import qs.services

// The pill's other faces: the "app will wait" message, the break card and the early-exit question.
Item {
    id: root

    required property string view
    property string appName
    property string appIcon
    property string appText
    readonly property var s: Study.session
    readonly property bool ready: Study.phase === "ready"
    readonly property Item current: view === "msg" ? message : view === "break" ? breakCard : view === "exit" ? exitCard : null

    // Keyboard: Enter held fills the hold button (a free session just finishes).
    function holdPress(): void {
        if (root.s?.blocks)
            hold.press();
        else
            Study.finish();
    }

    function holdRelease(): void {
        if (root.s?.blocks)
            hold.release();
    }

    signal keepStudying
    signal nextBlock

    implicitWidth: current?.implicitWidth ?? 0
    implicitHeight: current?.implicitHeight ?? 0

    component Face: Item {
        required property string name
        readonly property bool on: root.view === name

        opacity: on ? 1 : 0
        visible: opacity > 0

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }

    Face {
        id: message

        name: "msg"
        implicitWidth: msgRow.implicitWidth
        implicitHeight: msgRow.implicitHeight

        Row {
            id: msgRow

            leftPadding: Tokens.padding.small + Tokens.padding.extraSmall
            rightPadding: Tokens.padding.large
            topPadding: Tokens.padding.small - 1
            bottomPadding: Tokens.padding.small - 1
            spacing: Tokens.spacing.small + Tokens.spacing.extraSmall

            AppIcon {
                id: icon

                anchors.verticalCenter: parent.verticalCenter
                name: root.appIcon
                size: Tokens.font.icon.small.pointSize * 1.5
                scale: message.on ? 1 : 0.4
                rotation: message.on ? 0 : -30

                Behavior on scale {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
                Behavior on rotation {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
            }

            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.StyledText
                text: `<b>${root.appName}</b> ${root.appText}`
                font: Tokens.font.label.large
            }
        }
    }

    Face {
        id: breakCard

        name: "break"
        implicitWidth: breakCol.implicitWidth
        implicitHeight: breakCol.implicitHeight

        Column {
            id: breakCol

            width: Tokens.padding.extraExtraLarge * 7.5
            padding: Tokens.padding.large + Tokens.padding.extraSmall
            spacing: Tokens.spacing.small

            Row {
                spacing: Tokens.spacing.small

                MaterialIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.ready ? "self_improvement" : "coffee"
                    color: Colours.palette.m3onTertiaryContainer
                    fill: 1
                    fontStyle: Tokens.font.icon.medium
                }

                StyledText {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.ready ? "¿Seguimos?" : "Descanso"
                    color: Colours.palette.m3onTertiaryContainer
                    font: Tokens.font.title.large
                    animate: true
                }
            }

            StyledText {
                width: parent.width - parent.padding * 2
                wrapMode: Text.WordWrap
                text: !root.s ? "" : root.ready ? `Descanso terminado. Cuando quieras, empieza el bloque ${root.s.block + 1}.`
                                                : `Bloque ${root.s.blocksDone} hecho. Levántate, estira, bebe agua.`
                color: Colours.palette.m3onTertiaryContainer
                opacity: 0.85
                font: Tokens.font.body.medium
            }

            StyledRect {
                width: parent.width - parent.padding * 2
                height: Tokens.padding.extraSmall + 2
                radius: height / 2
                color: Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.15)

                StyledRect {
                    height: parent.height
                    radius: parent.radius
                    width: parent.width * (root.ready ? 0 : 1 - Study.progress)
                    color: Qt.alpha(Colours.palette.m3onTertiaryContainer, 0.6)

                    Behavior on width {
                        Anim {
                            type: Anim.StandardLarge
                        }
                    }
                }
            }

            ActionButton {
                kind: "tertiary"
                text: !root.s ? "" : root.ready ? `Empezar bloque ${root.s.block + 1}` : "Saltar descanso"
                onClicked: root.nextBlock()
            }
        }
    }

    Face {
        id: exitCard

        name: "exit"
        implicitWidth: exitCol.implicitWidth
        implicitHeight: exitCol.implicitHeight

        Column {
            id: exitCol

            width: Tokens.padding.extraExtraLarge * 7
            padding: Tokens.padding.large + Tokens.padding.extraSmall
            spacing: Tokens.spacing.small

            StyledText {
                text: "¿Terminar la sesión?"
                font: Tokens.font.title.large
            }

            StyledText {
                width: parent.width - parent.padding * 2
                bottomPadding: Tokens.spacing.small
                wrapMode: Text.WordWrap
                text: !root.s ? "" : (root.s.blocks ? `Llevas ${root.s.blocksDone} de ${root.s.blocks} bloques.` : `Llevas ${root.s.blocksDone} bloques.`)
                                     + " Lo que has hecho se guarda."
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.medium
            }

            Row {
                spacing: Tokens.spacing.small

                // A free session has no "early": a plain confirmation is enough.
                HoldButton {
                    id: hold

                    visible: !!root.s?.blocks
                    text: "Mantén para salir"
                    onCompleted: Study.finish()
                    onVisibleChanged: progress = 0
                }

                ActionButton {
                    visible: !root.s?.blocks
                    kind: "tonal"
                    text: "Terminar"
                    onClicked: Study.finish()
                }

                ActionButton {
                    kind: "text"
                    text: "Seguir"
                    onClicked: root.keepStudying()
                }
            }
        }
    }
}
