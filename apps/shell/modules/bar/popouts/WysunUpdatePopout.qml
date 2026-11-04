pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import "../../../services/WysunUpdateLogic.js" as Logic

// New commits in the Wysun source (`wysun update --check`): how many, when it was last checked,
// and the two actions. Updating opens a terminal because `wysun update` may ask for sudo.
ColumnLayout {
    id: root

    property real now: Date.now()

    width: 340
    spacing: Tokens.spacing.medium

    StyledText {
        Layout.topMargin: Tokens.padding.small
        text: "Actualización de Wysun"
        font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
    }

    StyledRect {
        Layout.fillWidth: true
        implicitHeight: card.implicitHeight + Tokens.padding.large * 2
        radius: Tokens.rounding.large
        color: Colours.tPalette.m3surfaceContainerHigh

        ColumnLayout {
            id: card

            anchors.fill: parent
            anchors.margins: Tokens.padding.large
            spacing: Tokens.spacing.small

            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.medium

                StyledRect {
                    implicitWidth: Tokens.sizes.bar.innerWidth
                    implicitHeight: implicitWidth
                    radius: Tokens.rounding.medium
                    color: Colours.palette.m3primaryContainer

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: "system_update"
                        color: Colours.palette.m3onPrimaryContainer
                        fill: 1
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    StyledText {
                        Layout.fillWidth: true
                        text: Logic.changes(WysunUpdate.behind, WysunUpdate.branch)
                        wrapMode: Text.Wrap
                        font: Tokens.font.title.small
                    }

                    StyledText {
                        Layout.fillWidth: true
                        text: WysunUpdate.checking ? "Comprobando…" : Logic.ago(WysunUpdate.checked, root.now)
                        color: Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.body.small
                    }
                }
            }

            StyledText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: WysunUpdate.error
                color: Colours.palette.m3error
                wrapMode: Text.Wrap
                font: Tokens.font.body.small
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.small

        IconTextButton {
            Layout.fillWidth: true
            icon: "download"
            text: "Actualizar"
            onClicked: WysunUpdate.apply()
        }

        IconTextButton {
            Layout.fillWidth: true
            type: IconTextButton.Text
            icon: "refresh"
            text: "Comprobar ahora"
            disabled: WysunUpdate.checking
            onClicked: WysunUpdate.check()
        }
    }

    // "Comprobado hace …" stays true while the popout is open.
    Timer {
        interval: 30 * 1000
        running: true
        repeat: true
        onTriggered: root.now = Date.now()
    }
}
