import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// One usage window: what is left, when it resets and how the pace looks.
ColumnLayout {
    id: root

    required property var limit
    property color colour: Colours.palette.m3primary
    property real now: Date.now()
    property bool compact
    property int resetCredits

    readonly property real remaining: 1 - limit.usedPercent / 100
    readonly property var pace: Format.pace(limit, now)
    readonly property color fill: remaining < 0.1 ? Colours.palette.m3error : colour

    function label(id: string): string {
        if (id === "session")
            return Tr.tr("Session");
        if (id === "weekly")
            return Tr.tr("Weekly");
        // TRANSLATORS: %1 = a model family with its own weekly limit, such as "opus"
        return Tr.tr("Weekly · %1").arg(id.replace(/^weekly_/, ""));
    }

    function paceText(): string {
        const p = root.pace;
        if (!p)
            return "";
        const delta = Math.round(p.delta);
        const state = Math.abs(delta) < 5 ? Tr.tr("On pace") : delta > 0 ? Tr.tr("Ahead (+%1%)").arg(delta) : Tr.tr("Behind (%1%)").arg(delta);
        const outlook = p.lasts ? Tr.tr("Lasts to reset") : Tr.tr("Runs out in %1").arg(Format.countdown(p.runsOutAt, root.now));
        return state + " · " + outlook;
    }

    spacing: Tokens.spacing.extraSmall

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.small

        StyledText {
            text: root.label(root.limit.id)
            font: root.compact ? Tokens.font.label.medium : Tokens.font.title.small
            color: root.compact ? Colours.palette.m3onSurfaceVariant : Colours.palette.m3onSurface
        }

        Item {
            Layout.fillWidth: true
        }

        StyledText {
            text: Math.round(root.remaining * 100) + "%"
            font: (root.compact ? Tokens.font.title.builders.small : Tokens.font.headline.builders.small).weight(Font.Bold).build()
            color: root.fill
        }

        StyledText {
            Layout.alignment: Qt.AlignBaseline
            text: Tr.trCtx("left", "remaining share of a usage limit")
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    LimitBar {
        Layout.fillWidth: true
        implicitHeight: root.compact ? Tokens.sizes.aiUsage.typeBarHeight : Tokens.sizes.aiUsage.limitBarHeight
        fraction: root.remaining
        fillColour: root.fill
        resetText: root.compact ? "" : Format.countdown(root.limit.resetsAt, root.now)
        credits: root.compact ? 0 : root.resetCredits
    }

    RowLayout {
        Layout.fillWidth: true
        visible: !root.compact
        spacing: Tokens.spacing.small

        StyledText {
            Layout.fillWidth: true
            text: root.paceText()
            font: Tokens.font.label.small
            color: (root.pace && !root.pace.lasts) ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
            elide: Text.ElideRight
        }

        StyledText {
            visible: !!root.limit.resetsAt
            // TRANSLATORS: %1 = a reset time such as "Fri 14:00"
            text: Tr.tr("Resets %1").arg(Qt.formatDateTime(new Date((root.limit.resetsAt ?? 0) * 1000), root.limit.windowMinutes > 1440 ? "ddd hh:mm" : "hh:mm"))
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }
    }
}
