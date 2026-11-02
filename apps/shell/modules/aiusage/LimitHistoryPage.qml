pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// One limit over its window: what is left at each recorded refresh (limit.history), the even-use
// guide, the projection at the current pace, and the previous windows with their cost (limit.windows).
ColumnLayout {
    id: root

    required property var account
    required property var limit
    property real now: Date.now()

    signal backRequested

    readonly property real span: (limit.windowMinutes ?? 0) * 60
    readonly property real start: (limit.resetsAt ?? 0) - span
    readonly property var pace: AiUsage.pace(limit)
    readonly property bool guide: AiUsage.settings.paceGuide

    spacing: Tokens.spacing.small

    PageHeader {
        title: AiUsage.limitTitle(root.limit) + " · " + AiUsage.names(root.account).label
        onBackRequested: root.backRequested()

        Chip {
            text: (AiUsage.settings.showUsed ? Tr.tr("%1% used") : Tr.tr("%1% left")).arg(Math.round(AiUsage.settings.showUsed ? root.limit.usedPercent : 100 - root.limit.usedPercent))
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small

        StyledText {
            Layout.fillWidth: true
            text: Tr.tr("What is left in this window")
            font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
            color: Colours.palette.m3onSurfaceVariant
        }

        StyledText {
            text: root.limit.resetsAt ? Tr.tr("Resets in %1").arg(Format.countdown(root.limit.resetsAt, root.now)) : Tr.tr("No active window")
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    Canvas {
        id: chart

        readonly property real axis: Tokens.spacing.extraExtraLarge
        readonly property real pad: Tokens.spacing.medium
        readonly property color line: Colours.palette.m3primary
        readonly property color grid: Colours.palette.m3outlineVariant
        readonly property color guideColour: Colours.palette.m3outline
        readonly property color good: Colours.palette.m3success
        readonly property color bad: Colours.palette.m3error
        readonly property color text: Colours.palette.m3outline
        readonly property var points: root.limit.history ?? []

        Layout.fillWidth: true
        implicitHeight: Tokens.sizes.aiUsage.chartHeight + Tokens.spacing.large

        onPointsChanged: requestPaint()
        onLineChanged: requestPaint()
        onWidthChanged: requestPaint()

        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            const w = width - axis, h = height - Tokens.spacing.large;
            const X = t => axis + Math.max(0, Math.min(1, (t - root.start) / Math.max(1, root.span))) * w;
            const Y = left => pad + (h - pad) * (1 - left / 100);
            ctx.font = `${Tokens.font.label.small.pointSize}pt "${Tokens.font.label.small.family}"`;
            ctx.fillStyle = text;
            ctx.strokeStyle = grid;
            ctx.lineWidth = 1;
            for (const v of [0, 50, 100]) {
                ctx.beginPath();
                ctx.moveTo(axis, Y(v));
                ctx.lineTo(width, Y(v));
                ctx.stroke();
                ctx.textAlign = "right";
                ctx.fillText(v + "%", axis - Tokens.spacing.small, Y(v) + Tokens.spacing.extraSmall);
            }
            if (!root.limit.resetsAt)
                return;
            if (root.guide) {
                ctx.strokeStyle = guideColour;
                ctx.setLineDash([6, 5]);
                ctx.beginPath();
                ctx.moveTo(X(root.start), Y(100));
                ctx.lineTo(X(root.limit.resetsAt), Y(0));
                ctx.stroke();
                ctx.setLineDash([]);
            }
            const nowS = root.now / 1000;
            const pts = points.map(p => [p[0], 100 - p[1]]).concat([[nowS, 100 - root.limit.usedPercent]]);
            ctx.fillStyle = Qt.alpha(line, 0.16);
            ctx.beginPath();
            ctx.moveTo(X(pts[0][0]), Y(0));
            for (const p of pts)
                ctx.lineTo(X(p[0]), Y(p[1]));
            ctx.lineTo(X(nowS), Y(0));
            ctx.closePath();
            ctx.fill();
            ctx.strokeStyle = line;
            ctx.lineWidth = Tokens.sizes.aiUsage.chartLineWidth;
            ctx.beginPath();
            pts.forEach((p, i) => i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1])));
            ctx.stroke();
            if (root.pace && !root.pace.early && !root.pace.exhausted) {
                const end = root.pace.lasts ? root.limit.resetsAt : nowS + root.pace.runsOutIn;
                const left = root.pace.lasts ? Math.max(0, 100 - root.limit.usedPercent * (root.limit.resetsAt - root.start) / Math.max(1, nowS - root.start)) : 0;
                ctx.strokeStyle = root.pace.lasts ? good : bad;
                ctx.setLineDash([2, 4]);
                ctx.beginPath();
                ctx.moveTo(X(nowS), Y(100 - root.limit.usedPercent));
                ctx.lineTo(X(end), Y(left));
                ctx.stroke();
                ctx.setLineDash([]);
            }
            ctx.fillStyle = line;
            ctx.beginPath();
            ctx.arc(X(nowS), Y(100 - root.limit.usedPercent), Tokens.spacing.extraSmall + 1, 0, 2 * Math.PI);
            ctx.fill();
            ctx.fillStyle = text;
            ctx.textAlign = "left";
            ctx.fillText(Tr.tr("start"), axis, height - 2);
            ctx.textAlign = "right";
            ctx.fillText(Tr.tr("reset"), width, height - 2);
        }
    }

    StyledText {
        visible: (root.limit.history ?? []).length < 3
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        wrapMode: Text.WordWrap
        text: Tr.tr("The line fills in as Wysun records this limit on each refresh.")
        font: Tokens.font.label.small
        color: Colours.palette.m3onSurfaceVariant
    }

    Banner {
        visible: !!root.pace && !root.pace.early
        icon: root.pace?.lasts ? "speed" : "warning"
        tone: root.pace?.lasts ? Colours.palette.m3primary : Colours.palette.m3error
        title: root.pace?.exhausted ? Tr.tr("This limit is spent until the reset") : root.pace?.lasts ? (root.pace.delta <= 0 ? Tr.tr("You are %1% below even use").arg(-root.pace.delta) : Tr.tr("You are %1% above even use").arg(root.pace.delta)) : Tr.tr("At this pace it runs out in %1").arg(Format.countdown(root.now / 1000 + (root.pace?.runsOutIn ?? 0), root.now))
        body: root.pace?.lasts ? Tr.tr("At this pace it lasts until the reset.") : ""
    }

    Divider {
        Layout.topMargin: Tokens.spacing.small
    }

    StyledText {
        Layout.leftMargin: Tokens.padding.small
        Layout.topMargin: Tokens.spacing.small
        text: Tr.tr("Previous windows")
        font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
        color: Colours.palette.m3onSurfaceVariant
    }

    StyledText {
        visible: !(root.limit.windows ?? []).length
        Layout.leftMargin: Tokens.padding.small
        text: Tr.tr("None recorded yet.")
        font: Tokens.font.label.small
        color: Colours.palette.m3onSurfaceVariant
    }

    Repeater {
        model: root.limit.windows ?? []

        RowLayout {
            id: window

            required property var modelData

            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.rightMargin: Tokens.padding.small
            spacing: Tokens.spacing.medium

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    text: Tr.tr("Ended %1").arg(Qt.formatDateTime(new Date(window.modelData.endedAt * 1000), "ddd d MMM hh:mm"))
                    font: Tokens.font.label.medium
                }

                StyledText {
                    text: window.modelData.exhaustedAt ? Tr.tr("spent on %1").arg(Qt.formatDateTime(new Date(window.modelData.exhaustedAt * 1000), "ddd hh:mm")) : Tr.tr("ended with %1% left").arg(Math.round(100 - window.modelData.usedPercent))
                    font: Tokens.font.label.small
                    color: window.modelData.exhaustedAt ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
                }
            }

            StyledRect {
                implicitWidth: Tokens.spacing.extraExtraLarge * 2
                implicitHeight: Tokens.sizes.aiUsage.typeBarHeight
                radius: Tokens.rounding.full
                color: Qt.alpha(Colours.palette.m3onSurface, 0.09)

                StyledRect {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: parent.width * Math.min(1, window.modelData.usedPercent / 100)
                    radius: Tokens.rounding.full
                    color: AiUsage.severityColour(window.modelData.usedPercent)
                }
            }

            StyledText {
                Layout.preferredWidth: Tokens.spacing.extraLarge + Tokens.spacing.medium
                horizontalAlignment: Text.AlignRight
                text: Math.round(window.modelData.usedPercent) + "%"
                font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
            }

            StyledText {
                Layout.preferredWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.medium
                horizontalAlignment: Text.AlignRight
                text: Format.money(window.modelData.cost)
                font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
            }
        }
    }
}
