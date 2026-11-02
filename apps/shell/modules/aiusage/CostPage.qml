pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services
import "Format.js" as Format

// Cost or tokens of one account: daily bars (a day opens its hours), cost per weekly window,
// a year of activity and a daily ledger, with the split by model and by project.
ColumnLayout {
    id: root

    required property var account
    property real now: Date.now()
    property string tab: "daily"
    property int day: -1
    property int hovered: -1
    property bool showAll

    signal backRequested

    readonly property bool byCost: AiUsage.metric === "cost"
    readonly property var range: account.usage?.[AiUsage.range] ?? null
    readonly property var series: range?.series?.[account.id] ?? null
    readonly property var hours: account.usage?.hours90 ?? null
    readonly property var hourSeries: hours?.series?.[account.id] ?? null
    readonly property real dayStart: range && day >= 0 ? range.start + day * 86400 : 0
    readonly property var hourValues: {
        if (day < 0 || !hours || !hourSeries)
            return [];
        const out = [];
        const first = Math.round((dayStart - hours.start) / 3600);
        for (let i = 0; i < 24; i++)
            out.push((byCost ? hourSeries.cost : hourSeries.tokens)[first + i] ?? 0);
        return out;
    }
    readonly property var values: day >= 0 ? hourValues : series ? (byCost ? series.cost : series.tokens) : []

    function format(value: real): string {
        return byCost ? Format.money(value) : Format.tokens(value);
    }

    function dateAt(start: real, index: int, step: int): string {
        return Qt.formatDate(new Date((start + index * step) * 1000), "d MMM");
    }

    spacing: Tokens.spacing.small

    PageHeader {
        title: Tr.tr("Cost · %1").arg(AiUsage.names(root.account).label)
        onBackRequested: root.backRequested()

        Segmented {
            current: AiUsage.metric
            options: [{ value: "cost", text: Tr.tr("Cost") }, { value: "tokens", text: Tr.tr("Tokens") }]
            onSelected: value => AiUsage.metric = value
        }
    }

    Segmented {
        Layout.alignment: Qt.AlignHCenter
        current: root.tab
        options: [
            { value: "daily", text: Tr.tr("Daily") },
            { value: "windows", text: Tr.tr("Per window") },
            { value: "activity", text: Tr.tr("Activity") },
            { value: "ledger", text: Tr.tr("Ledger") }
        ]
        onSelected: value => {
            root.tab = value;
            root.day = -1;
        }
    }

    // Daily
    ColumnLayout {
        Layout.fillWidth: true
        visible: root.tab === "daily"
        spacing: Tokens.spacing.small

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    text: root.format(root.values.reduce((a, b) => a + b, 0))
                    font: Tokens.font.headline.builders.medium.weight(Font.DemiBold).build()
                }

                StyledText {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    text: root.day >= 0 ? Qt.formatDate(new Date(root.dayStart * 1000), "dddd d MMMM") + " · " + Tr.tr("by hour") : Tr.tr("last %1 days · %2 a day").arg(root.values.length).arg(root.format(root.values.reduce((a, b) => a + b, 0) / Math.max(1, root.values.length))) + (root.byCost ? " · " + Tr.tr("estimate at API prices") : "")
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }

            TextButton {
                visible: root.day >= 0
                type: TextButton.Text
                text: Tr.tr("Back to days")
                onClicked: root.day = -1
            }

            Segmented {
                visible: root.day < 0
                current: AiUsage.range
                options: [{ value: "7d", text: Tr.tr("7 d") }, { value: "30d", text: Tr.tr("30 d") }, { value: "90d", text: Tr.tr("90 d") }]
                onSelected: value => AiUsage.range = value
            }
        }

        BarChart {
            values: root.values
            formatValue: v => root.format(v)
            xLabels: root.day >= 0 ? ["00:00", "12:00", "23:00"] : root.range ? [root.dateAt(root.range.start, 0, 86400), root.dateAt(root.range.start, Math.floor(root.range.points / 2), 86400), Tr.tr("Today")] : []
            onHoveredChanged: root.hovered = hovered
            onPicked: index => {
                if (root.day < 0 && root.hours && root.range.start + index * 86400 >= root.hours.start)
                    root.day = index;
            }
        }

        // Inspector: the hovered bar, under the chart.
        StyledRect {
            Layout.fillWidth: true
            implicitHeight: inspect.implicitHeight + Tokens.padding.small * 2
            radius: Tokens.rounding.medium
            color: Colours.tPalette.m3surfaceContainer

            StyledText {
                id: inspect

                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: Tokens.padding.medium
                text: root.hovered < 0 ? (root.day < 0 ? Tr.tr("Hover a day to see it; click it to see its hours") : Tr.tr("Hover an hour to see it")) : (root.day >= 0 ? String(root.hovered).padStart(2, "0") + ":00" : Qt.formatDate(new Date((root.range.start + root.hovered * 86400) * 1000), "ddd d MMM")) + " · " + Format.money((root.day >= 0 ? root.hourSeries?.cost?.[Math.round((root.dayStart - root.hours.start) / 3600) + root.hovered] : root.series?.cost?.[root.hovered]) ?? 0) + " · " + Format.tokens((root.day >= 0 ? root.hourSeries?.tokens?.[Math.round((root.dayStart - root.hours.start) / 3600) + root.hovered] : root.series?.tokens?.[root.hovered]) ?? 0) + " " + Tr.tr("tokens")
                font: Tokens.font.label.medium
                color: root.hovered < 0 ? Colours.palette.m3onSurfaceVariant : Colours.palette.m3onSurface
            }
        }

        Divider {
            Layout.topMargin: Tokens.spacing.small
        }

        Breakdown {
            title: Tr.tr("By model")
            items: (root.range?.models ?? []).slice(0, Tokens.sizes.aiUsage.maxModels).map(m => ({
                        name: m.model,
                        share: root.byCost ? m.costShare : m.tokenShare,
                        value: root.byCost ? (m.cost === null ? "—" : Format.money(m.cost)) : Format.tokens(m.tokens),
                        icon: ""
                    }))
        }

        Divider {}

        Breakdown {
            title: Tr.tr("By project")
            items: (root.range?.projects ?? []).slice(0, Tokens.sizes.aiUsage.maxProjects).map(p => ({
                        name: p.name,
                        share: root.byCost ? p.costShare : p.tokenShare,
                        value: root.byCost ? Format.money(p.cost) : Format.tokens(p.tokens),
                        icon: "folder"
                    }))
        }
    }

    // Per weekly window
    ColumnLayout {
        id: windows

        readonly property var weekly: (root.account.limits ?? []).find(l => l.id === "weekly") ?? null
        readonly property real currentCost: {
            if (!weekly?.resetsAt || !root.hours || !root.hourSeries)
                return 0;
            const from = weekly.resetsAt - 7 * 86400;
            let sum = 0;
            for (let i = 0; i < root.hours.points; i++)
                if (root.hours.start + i * 3600 >= from)
                    sum += root.hourSeries.cost[i];
            return sum;
        }

        Layout.fillWidth: true
        visible: root.tab === "windows"
        spacing: Tokens.spacing.small

        StyledText {
            visible: !windows.weekly
            Layout.margins: Tokens.padding.small
            text: Tr.tr("This account has no weekly limit.")
            color: Colours.palette.m3onSurfaceVariant
        }

        Breakdown {
            visible: !!windows.weekly
            title: Tr.tr("Cost split at each weekly reset")
            items: windows.weekly ? [{
                        name: Tr.tr("Current window"),
                        share: Math.min(1, windows.weekly.usedPercent / 100),
                        value: Format.money(windows.currentCost),
                        icon: "schedule"
                    }].concat((windows.weekly.windows ?? []).map(w => ({
                            name: Tr.tr("Ended %1").arg(Qt.formatDate(new Date(w.endedAt * 1000), "d MMM")) + " · " + Math.round(w.usedPercent) + "%",
                            share: Math.min(1, w.usedPercent / 100),
                            value: Format.money(w.cost),
                            icon: w.exhaustedAt ? "block" : "history"
                        }))) : []
        }
    }

    // Activity: a year of tokens, one cell per day, weeks as columns.
    ColumnLayout {
        id: activity

        readonly property var year: root.account.usage?.["365d"] ?? null
        readonly property var days: year?.series?.[root.account.id]?.tokens ?? []
        readonly property real peak: Math.max(1, ...days)
        readonly property int offset: year ? new Date(year.start * 1000).getDay() : 0
        readonly property int active: days.filter(v => v > 0).length
        readonly property int streak: {
            let best = 0, run = 0;
            for (const v of days) {
                run = v > 0 ? run + 1 : 0;
                best = Math.max(best, run);
            }
            return best;
        }

        Layout.fillWidth: true
        visible: root.tab === "activity"
        spacing: Tokens.spacing.small

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small

            StyledText {
                Layout.fillWidth: true
                text: Tr.tr("Token activity · last year")
                font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
                color: Colours.palette.m3onSurfaceVariant
            }

            StyledText {
                text: Format.tokens(activity.days.reduce((a, b) => a + b, 0)) + " " + Tr.tr("tokens")
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }
        }

        Item {
            id: heat

            readonly property int columns: Math.ceil((activity.days.length + activity.offset) / 7)
            readonly property real gap: Tokens.padding.extraSmall / 2
            readonly property real cell: Math.floor((width - (columns - 1) * gap) / Math.max(1, columns))

            Layout.fillWidth: true
            implicitHeight: cell * 7 + gap * 6

            Repeater {
                model: activity.days

                StyledRect {
                    id: cell

                    required property real modelData
                    required property int index
                    readonly property int position: index + activity.offset

                    x: Math.floor(position / 7) * (heat.cell + heat.gap)
                    y: (position % 7) * (heat.cell + heat.gap)
                    width: heat.cell
                    height: heat.cell
                    radius: Tokens.rounding.extraSmall / 2
                    color: modelData > 0 ? Qt.alpha(Colours.palette.m3primary, 0.2 + 0.8 * Math.sqrt(modelData / activity.peak)) : Qt.alpha(Colours.palette.m3onSurface, 0.07)

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onContainsMouseChanged: root.hovered = containsMouse ? -2 - cell.index : -1
                    }
                }
            }
        }

        StyledText {
            Layout.leftMargin: Tokens.padding.small
            text: root.hovered <= -2 && activity.year ? Qt.formatDate(new Date((activity.year.start + (-2 - root.hovered) * 86400) * 1000), "ddd d MMM yyyy") + " · " + Format.tokens(activity.days[-2 - root.hovered]) + " " + Tr.tr("tokens") : Tr.tr("Longest streak: %1 days · active days: %2 of %3").arg(activity.streak).arg(activity.active).arg(activity.days.length)
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    // Ledger: one row per day, newest first.
    ColumnLayout {
        id: ledger

        readonly property var month: root.account.usage?.[root.showAll ? "90d" : "30d"] ?? null
        readonly property var rows: {
            const s = month?.series?.[root.account.id];
            if (!s)
                return [];
            const out = [];
            for (let i = month.points - 1; i >= 0; i--)
                out.push({ at: month.start + i * 86400, cost: s.cost[i], tokens: s.tokens[i], partial: !!s.unpriced?.[i] });
            return root.showAll ? out : out.slice(0, 14);
        }

        Layout.fillWidth: true
        visible: root.tab === "ledger"
        spacing: Tokens.spacing.extraSmall

        Repeater {
            model: ledger.rows

            RowLayout {
                id: entry

                required property var modelData

                Layout.fillWidth: true
                Layout.leftMargin: Tokens.padding.small
                Layout.rightMargin: Tokens.padding.small

                StyledText {
                    Layout.fillWidth: true
                    text: Qt.formatDate(new Date(entry.modelData.at * 1000), "ddd d MMM")
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                }

                StyledText {
                    text: Format.tokens(entry.modelData.tokens)
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                }

                StyledText {
                    Layout.preferredWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.large
                    horizontalAlignment: Text.AlignRight
                    text: (entry.modelData.partial ? "~" : "") + Format.money(entry.modelData.cost)
                    font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
                }
            }
        }

        TextButton {
            Layout.alignment: Qt.AlignHCenter
            type: TextButton.Text
            text: root.showAll ? Tr.tr("Show less") : Tr.tr("Show all")
            onClicked: root.showAll = !root.showAll
        }

        StyledText {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            wrapMode: Text.WordWrap
            text: Tr.tr("~ a day with a model of unknown price: only the priced part is counted.")
            font: Tokens.font.label.small
            color: Colours.palette.m3outline
        }
    }
}
