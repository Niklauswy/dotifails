pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// Cost or tokens over a range: total, legend, chart, totals, types and models.
// `usage` is a backend usage block ({ "24h": ..., "7d": ..., "30d": ... }) whose
// series are keyed by account id; `accounts` are the accounts to draw.
ColumnLayout {
    id: root

    property var usage: ({})
    property var accounts: []

    readonly property var current: usage?.[AiUsage.range] ?? null
    readonly property bool byCost: AiUsage.metric === "cost"
    readonly property real whole: byCost ? current?.totals.cost ?? 0 : current?.totals.processed ?? 0

    function formatMetric(value: real): string {
        return byCost ? Format.money(value) : Format.tokens(value);
    }

    function axisLabels(u: var): var {
        if (!u)
            return [];
        const format = u.step === 3600 ? "h AP" : "MMM d";
        const at = i => Qt.formatDateTime(new Date((u.start + i * u.step) * 1000), format);
        const last = u.points - 1;
        return [
            { position: 0, text: at(0) },
            { position: 0.5, text: at(Math.round(last / 2)) },
            { position: 1, text: at(last) }
        ];
    }

    spacing: Tokens.spacing.medium

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.small

        Segmented {
            current: AiUsage.metric
            options: [
                { value: "cost", text: Tr.tr("Cost") },
                { value: "tokens", text: Tr.tr("Tokens") }
            ]
            onSelected: value => AiUsage.metric = value
        }

        Item {
            Layout.fillWidth: true
        }

        Segmented {
            current: AiUsage.range
            options: [
                { value: "24h", text: Tr.tr("24h") },
                { value: "7d", text: Tr.tr("7 days") },
                { value: "30d", text: Tr.tr("30 days") },
                { value: "90d", text: Tr.tr("90 days") }
            ]
            onSelected: value => AiUsage.range = value
        }
    }

    Card {
        Layout.fillWidth: true
        visible: !!root.current

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.large

                ColumnLayout {
                    Layout.alignment: Qt.AlignTop
                    spacing: 0

                    StyledText {
                        text: root.formatMetric(root.whole)
                        font: Tokens.font.headline.builders.large.weight(Font.Bold).build()
                        color: Colours.palette.m3primary
                    }

                    StyledText {
                        // TRANSLATORS: %1 = number of sessions
                        text: Tr.tr("%1 sessions").arg(root.current?.sessionCount ?? 0) + (root.byCost ? " · " + Tr.tr("API estimate") : "")
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: Tokens.spacing.extraSmall
                    visible: root.accounts.length > 1

                    Repeater {
                        model: root.accounts

                        RowLayout {
                            id: legend

                            required property var modelData
                            readonly property var totals: root.current?.byKey[modelData.id] ?? { tokens: 0, cost: 0 }
                            readonly property real value: root.byCost ? totals.cost : totals.tokens

                            Layout.fillWidth: true
                            spacing: Tokens.spacing.small

                            ProviderLogo {
                                provider: legend.modelData.provider
                                colour: AiUsage.colour(legend.modelData.id)
                                size: Tokens.spacing.large
                            }

                            StyledText {
                                Layout.fillWidth: true
                                text: legend.modelData.providerName + " · " + legend.modelData.label
                                font: Tokens.font.body.small
                                elide: Text.ElideRight
                            }

                            StyledText {
                                text: Format.percent(root.whole ? legend.value / root.whole : 0)
                                font: Tokens.font.label.small
                                color: Colours.palette.m3onSurfaceVariant
                            }

                            StyledText {
                                text: root.formatMetric(legend.value)
                                font: Tokens.font.body.builders.small.weight(Font.Medium).build()
                            }
                        }
                    }
                }
            }

            UsageChart {
                Layout.fillWidth: true
                Layout.preferredHeight: Tokens.sizes.aiUsage.chartHeight
                formatValue: v => root.formatMetric(v)
                xLabels: root.axisLabels(root.current)
                series: root.accounts.slice().reverse().map(a => ({
                            values: root.current?.series[a.id]?.[root.byCost ? "cost" : "tokens"] ?? [],
                            colour: AiUsage.colour(a.id)
                        }))
            }
        }
    }

    Card {
        Layout.fillWidth: true
        visible: !!root.current

        ColumnLayout {
            id: types

            readonly property var parts: [
                { label: Tr.tr("Input"), value: root.current?.totals.input ?? 0, colour: Colours.palette.m3primary },
                { label: Tr.tr("Cache read"), value: root.current?.totals.cacheRead ?? 0, colour: Colours.palette.m3primaryContainer },
                { label: Tr.tr("Cache write"), value: root.current?.totals.cacheWrite ?? 0, colour: Colours.palette.m3tertiary },
                { label: Tr.tr("Output"), value: root.current?.totals.output ?? 0, colour: Colours.palette.m3secondary }
            ]
            readonly property real total: Math.max(1, root.current?.totals.processed ?? 0)

            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            GridLayout {
                Layout.fillWidth: true
                columns: 3
                rowSpacing: Tokens.spacing.small
                columnSpacing: Tokens.spacing.medium

                Repeater {
                    model: [
                        { label: Tr.tr("Processed"), value: Format.tokens(root.current?.totals.processed) },
                        { label: Tr.tr("Cached input"), value: Format.tokens(root.current?.totals.cacheRead) },
                        { label: Tr.tr("Uncached input"), value: Format.tokens(root.current?.totals.input) },
                        { label: Tr.tr("Output"), value: Format.tokens(root.current?.totals.output) },
                        { label: Tr.tr("Cache write"), value: Format.tokens(root.current?.totals.cacheWrite) },
                        { label: Tr.tr("Cache savings"), value: Format.money(root.current?.totals.savings) }
                    ]

                    ColumnLayout {
                        id: stat

                        required property var modelData

                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        spacing: 0

                        StyledText {
                            Layout.fillWidth: true
                            text: stat.modelData.label
                            font: Tokens.font.label.small
                            color: Colours.palette.m3onSurfaceVariant
                            elide: Text.ElideRight
                        }

                        StyledText {
                            text: stat.modelData.value
                            font: Tokens.font.title.builders.small.weight(Font.DemiBold).build()
                        }
                    }
                }
            }

            Row {
                id: typeBar

                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall / 2

                Repeater {
                    model: types.parts

                    StyledRect {
                        required property var modelData

                        visible: modelData.value > 0
                        // Keep tiny shares visible as a sliver.
                        width: Math.max(Tokens.sizes.aiUsage.typeBarHeight, (typeBar.width - typeBar.spacing * 3) * modelData.value / types.total)
                        height: Tokens.sizes.aiUsage.typeBarHeight
                        radius: Tokens.rounding.full
                        color: modelData.colour
                    }
                }
            }

            Flow {
                Layout.fillWidth: true
                spacing: Tokens.spacing.medium

                Repeater {
                    model: types.parts

                    Row {
                        id: part

                        required property var modelData

                        spacing: Tokens.spacing.extraSmall

                        StyledRect {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Tokens.spacing.small
                            height: Tokens.spacing.small
                            radius: Tokens.rounding.full
                            color: part.modelData.colour
                        }

                        StyledText {
                            text: part.modelData.label
                            font: Tokens.font.label.small
                            color: Colours.palette.m3onSurfaceVariant
                        }

                        StyledText {
                            text: Format.tokens(part.modelData.value)
                            font: Tokens.font.label.small
                        }
                    }
                }
            }
        }
    }

    Card {
        Layout.fillWidth: true
        visible: models.count > 0

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.small

                StyledText {
                    Layout.fillWidth: true
                    text: Tr.tr("Models")
                    font: Tokens.font.title.small
                }

                Repeater {
                    model: [Tr.tr("Cost"), Tr.tr("Share"), Tr.tr("Tokens")]

                    StyledText {
                        required property string modelData

                        Layout.preferredWidth: Tokens.sizes.aiUsage.width / 8
                        horizontalAlignment: Text.AlignRight
                        text: modelData
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }
            }

            Repeater {
                id: models

                model: (root.current?.models ?? []).filter(m => m.tokens > 0).slice(0, Tokens.sizes.aiUsage.maxModels)

                ColumnLayout {
                    id: modelRow

                    required property var modelData
                    readonly property real share: root.byCost ? modelData.costShare : modelData.tokenShare
                    readonly property color colour: modelData.provider === "claude" ? Colours.palette.m3tertiary : Colours.palette.m3primary

                    Layout.fillWidth: true
                    spacing: Tokens.spacing.extraSmall

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Tokens.spacing.small

                        ProviderLogo {
                            provider: modelRow.modelData.provider
                            colour: modelRow.colour
                            size: Tokens.spacing.large
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: modelRow.modelData.model
                            font: Tokens.font.body.small
                            elide: Text.ElideRight
                        }

                        StyledText {
                            Layout.preferredWidth: Tokens.sizes.aiUsage.width / 8
                            horizontalAlignment: Text.AlignRight
                            text: modelRow.modelData.cost === null ? Tr.tr("Unpriced") : Format.money(modelRow.modelData.cost)
                            font: Tokens.font.body.small
                            color: modelRow.modelData.cost === null ? Colours.palette.m3outline : Colours.palette.m3onSurface
                        }

                        StyledText {
                            Layout.preferredWidth: Tokens.sizes.aiUsage.width / 8
                            horizontalAlignment: Text.AlignRight
                            text: Format.percent(modelRow.share)
                            font: Tokens.font.body.small
                            color: Colours.palette.m3onSurfaceVariant
                        }

                        StyledText {
                            Layout.preferredWidth: Tokens.sizes.aiUsage.width / 8
                            horizontalAlignment: Text.AlignRight
                            text: Format.tokens(modelRow.modelData.tokens)
                            font: Tokens.font.body.small
                            color: Colours.palette.m3onSurfaceVariant
                        }
                    }

                    StyledRect {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Tokens.sizes.aiUsage.modelBarHeight
                        radius: Tokens.rounding.full
                        color: Colours.tPalette.m3surfaceContainerHighest

                        StyledRect {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            width: Math.max(parent.height, parent.width * modelRow.share)
                            radius: Tokens.rounding.full
                            color: modelRow.colour

                            Behavior on width {
                                Anim {}
                            }
                        }
                    }
                }
            }
        }
    }

    Card {
        Layout.fillWidth: true
        visible: projects.count > 0

        StyledText {
            text: Tr.tr("Projects")
            font: Tokens.font.title.small
        }

        Repeater {
            id: projects

            model: (root.current?.projects ?? []).filter(p => p.tokens > 0).slice(0, Tokens.sizes.aiUsage.maxProjects)

            ColumnLayout {
                id: project

                required property var modelData
                readonly property real share: root.byCost ? modelData.costShare : modelData.tokenShare

                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.small

                    MaterialIcon {
                        text: project.modelData.name === "~" ? "home" : "folder"
                        color: Colours.palette.m3primary
                        fontStyle: Tokens.font.icon.small
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        StyledText {
                            Layout.fillWidth: true
                            text: project.modelData.name
                            font: Tokens.font.body.builders.small.weight(Font.Medium).build()
                            elide: Text.ElideRight
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: {
                                // TRANSLATORS: %1 = number of sessions
                                const sessions = Tr.tr("%1 sessions").arg(project.modelData.sessions);
                                // TRANSLATORS: %1 = number of agent worktrees folded into the project
                                const trees = project.modelData.worktrees > 0 ? " · " + Tr.tr("%1 worktrees").arg(project.modelData.worktrees) : "";
                                return sessions + trees + (project.modelData.path ? " · " + project.modelData.path : "");
                            }
                            font: Tokens.font.label.small
                            color: Colours.palette.m3onSurfaceVariant
                            elide: Text.ElideMiddle
                        }
                    }

                    Repeater {
                        model: project.modelData.providers

                        ProviderLogo {
                            required property string modelData

                            provider: modelData
                            colour: Colours.palette.m3onSurfaceVariant
                            size: Tokens.spacing.large
                        }
                    }

                    StyledText {
                        Layout.preferredWidth: Tokens.sizes.aiUsage.width / 8
                        horizontalAlignment: Text.AlignRight
                        text: root.formatMetric(root.byCost ? project.modelData.cost : project.modelData.tokens)
                        font: Tokens.font.body.small
                    }

                    StyledText {
                        Layout.preferredWidth: Tokens.sizes.aiUsage.width / 8
                        horizontalAlignment: Text.AlignRight
                        text: Format.percent(project.share)
                        font: Tokens.font.body.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }

                StyledRect {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Tokens.sizes.aiUsage.modelBarHeight
                    radius: Tokens.rounding.full
                    color: Colours.tPalette.m3surfaceContainerHighest

                    StyledRect {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: Math.max(parent.height, parent.width * project.share)
                        radius: Tokens.rounding.full
                        color: Colours.palette.m3primary

                        Behavior on width {
                            Anim {}
                        }
                    }
                }
            }
        }
    }
}
