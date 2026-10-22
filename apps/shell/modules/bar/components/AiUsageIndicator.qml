import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.aiusage as AiUsagePanel

// The tightest AI limit as a small ring; red at the alert threshold. Opens the AI usage panel.
Item {
    id: root

    required property ScreenState screenState

    readonly property var tightest: AiUsage.tightest
    readonly property real remaining: tightest ? tightest.remaining / 100 : 0
    readonly property bool low: tightest && tightest.remaining <= Tokens.sizes.aiUsage.alertThreshold
    readonly property color colour: low ? Colours.palette.m3error : tightest ? AiUsage.colour(tightest.account.id) : Colours.palette.m3outline

    visible: !!tightest
    implicitWidth: Tokens.sizes.bar.innerWidth
    implicitHeight: layout.implicitHeight + Tokens.padding.small

    StateLayer {
        radius: Tokens.rounding.full
        onClicked: root.screenState.aiUsage = !root.screenState.aiUsage
    }

    ColumnLayout {
        id: layout

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall / 2

        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: Tokens.sizes.aiUsage.barIndicatorSize
            implicitHeight: implicitWidth

            CircularProgress {
                anchors.fill: parent
                implicitSize: parent.implicitWidth
                strokeWidth: Tokens.padding.extraSmall / 2
                value: root.remaining
                fgColour: root.colour
                bgColour: Qt.alpha(root.colour, 0.2)
            }

            AiUsagePanel.ProviderLogo {
                anchors.centerIn: parent
                provider: root.tightest?.account.provider ?? ""
                colour: root.colour
                size: parent.implicitWidth / 2
            }
        }

        StyledText {
            Layout.alignment: Qt.AlignHCenter
            text: Math.round(root.tightest?.remaining ?? 0) + "%"
            font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
            color: root.colour
        }
    }
}
