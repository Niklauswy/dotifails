import QtQuick
import Wysun.Config
import qs.components
import qs.services

// Remaining quota: solid fill for what is left, hatching for what is used.
Item {
    id: root

    property real fraction
    property color fillColour: Colours.palette.m3primary
    property color trackColour: Qt.alpha(fillColour, 0.1)
    property color hatchColour: Qt.alpha(fillColour, 0.28)
    property string valueText
    property string resetText
    // Codex reset credits available for this window.
    property int credits

    implicitHeight: Tokens.sizes.aiUsage.limitBarHeight

    onHatchColourChanged: hatch.requestPaint()

    StyledRect {
        anchors.fill: parent
        radius: Tokens.rounding.small
        color: root.trackColour
    }

    Canvas {
        id: hatch

        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d");
            const r = Math.min(Tokens.rounding.small, height / 2);
            ctx.reset();
            ctx.beginPath();
            ctx.roundedRect(0, 0, width, height, r, r);
            ctx.clip();
            ctx.strokeStyle = root.hatchColour;
            ctx.lineWidth = 1;
            const step = Tokens.sizes.aiUsage.hatchSpacing;
            ctx.beginPath();
            for (let x = -height; x < width + height; x += step) {
                ctx.moveTo(x, height);
                ctx.lineTo(x + height, 0);
            }
            ctx.stroke();
        }
    }

    StyledRect {
        id: fill

        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Math.max(root.fraction > 0 ? height : 0, parent.width * Math.max(0, Math.min(1, root.fraction)))
        radius: Tokens.rounding.small
        color: root.fillColour

        Behavior on width {
            Anim {}
        }
    }

    StyledText {
        anchors.left: parent.left
        anchors.leftMargin: Tokens.padding.small
        anchors.verticalCenter: parent.verticalCenter
        text: root.valueText
        font: Tokens.font.label.builders.small.weight(Font.DemiBold).build()
        color: Colours.palette.m3surface
        visible: root.valueText.length > 0 && fill.width > implicitWidth + Tokens.padding.small * 2
    }

    StyledRect {
        anchors.right: parent.right
        anchors.rightMargin: Tokens.padding.extraSmall
        anchors.verticalCenter: parent.verticalCenter
        visible: root.resetText.length > 0 || root.credits > 0
        implicitWidth: reset.implicitWidth + Tokens.padding.small * 2
        implicitHeight: parent.height - Tokens.padding.extraSmall * 2
        radius: Tokens.rounding.extraSmall
        color: Colours.tPalette.m3surfaceContainer

        Row {
            id: reset

            anchors.centerIn: parent
            spacing: Tokens.spacing.extraSmall

            MaterialIcon {
                anchors.verticalCenter: parent.verticalCenter
                text: "autorenew"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }

            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.resetText.length > 0
                text: root.resetText
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurface
            }

            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.credits > 0 && root.resetText.length > 0
                text: "·"
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }

            MaterialIcon {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.credits > 0
                text: "confirmation_number"
                color: root.fillColour
                fontStyle: Tokens.font.icon.small
            }

            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.credits > 0
                text: root.credits
                font: Tokens.font.label.builders.small.weight(Font.Bold).build()
                color: Colours.palette.m3onSurface
            }
        }
    }
}
