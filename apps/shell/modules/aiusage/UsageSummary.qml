pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.services
import "../../services/AiUsageLogic.js" as Logic
import "Format.js" as Format

// What the visible accounts add up to over a range: tokens and how they split, what the cache saved,
// and the models and projects that took the most.
ColumnLayout {
    id: root

    property string range: "30d"

    readonly property bool byCost: AiUsage.metric === "cost"
    readonly property var sum: Logic.aggregateUsage(AiUsage.visibleAccounts, range)
    readonly property var totals: sum.totals
    // The share of everything the models read that came from the cache.
    readonly property real cacheHit: {
        const read = totals.input + totals.cacheRead + totals.cacheWrite;
        return read ? totals.cacheRead / read : 0;
    }
    readonly property var kinds: [
        { name: Tr.tr("Cache read"), value: totals.cacheRead, colour: Colours.palette.m3primary },
        { name: Tr.tr("Cache write"), value: totals.cacheWrite, colour: Colours.palette.m3tertiary },
        { name: Tr.tr("Input"), value: totals.input, colour: Colours.palette.m3secondary },
        { name: Tr.tr("Output"), value: totals.output, colour: Colours.palette.m3outline }
    ]

    Layout.fillWidth: true
    spacing: Tokens.spacing.small

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.topMargin: Tokens.spacing.small
        spacing: Tokens.spacing.small

        StyledText {
            Layout.fillWidth: true
            text: Tr.tr("All accounts")
            font: Tokens.font.title.small
        }

        Segmented {
            current: AiUsage.metric
            options: [{ value: "cost", text: Tr.tr("Cost") }, { value: "tokens", text: Tr.tr("Tokens") }]
            onSelected: value => AiUsage.metric = value
        }

        Segmented {
            current: root.range
            options: [{ value: "7d", text: "7d" }, { value: "30d", text: "30d" }, { value: "90d", text: "90d" }]
            onSelected: value => root.range = value
        }
    }

    Flow {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small
        spacing: Tokens.spacing.large

        Stat {
            label: Tr.tr("Tokens")
            value: Format.tokens(root.totals.processed)
        }

        Stat {
            label: Tr.tr("Spent")
            value: Format.money(root.totals.cost)
        }

        Stat {
            label: Tr.tr("Cache hit rate")
            value: Format.percent(root.cacheHit)
        }

        Stat {
            label: Tr.tr("Cache saved")
            value: Format.money(root.totals.savings)
        }

        Stat {
            label: Tr.tr("Sessions")
            value: String(root.sum.sessions)
        }
    }

    // How the tokens split.
    Row {
        id: split

        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small
        Layout.preferredHeight: Tokens.sizes.aiUsage.typeBarHeight
        spacing: 2

        Repeater {
            model: root.kinds

            StyledRect {
                required property var modelData

                visible: modelData.value > 0
                width: Math.max(2, (split.width - split.spacing * 3) * modelData.value / Math.max(1, root.totals.processed))
                height: split.height
                radius: Tokens.rounding.full
                color: modelData.colour
            }
        }
    }

    Flow {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small
        spacing: Tokens.spacing.medium

        Repeater {
            model: root.kinds

            Row {
                id: kind

                required property var modelData

                spacing: Tokens.spacing.extraSmall

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    implicitWidth: Tokens.spacing.small
                    implicitHeight: implicitWidth
                    radius: width / 2
                    color: kind.modelData.colour
                }

                StyledText {
                    text: kind.modelData.name + " " + Format.tokens(kind.modelData.value)
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }
        }
    }

    Breakdown {
        title: Tr.tr("Top models")
        items: root.sum.models.slice(0, Tokens.sizes.aiUsage.maxModels).map(m => ({
                    name: m.model,
                    share: root.byCost ? m.costShare : m.tokenShare,
                    value: root.byCost ? (m.cost === null ? "—" : Format.money(m.cost)) : Format.tokens(m.tokens),
                    icon: ""
                }))
    }

    Breakdown {
        title: Tr.tr("Top projects")
        items: root.sum.projects.slice(0, Tokens.sizes.aiUsage.maxProjects).map(p => ({
                    name: p.name,
                    share: root.byCost ? p.costShare : p.tokenShare,
                    value: root.byCost ? Format.money(p.cost ?? 0) : Format.tokens(p.tokens),
                    icon: "folder"
                }))
    }

    component Stat: ColumnLayout {
        id: stat

        property string label
        property string value

        spacing: 0

        StyledText {
            text: stat.label
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }

        StyledText {
            text: stat.value
            font: Tokens.font.title.builders.small.weight(Font.DemiBold).build()
        }
    }
}
