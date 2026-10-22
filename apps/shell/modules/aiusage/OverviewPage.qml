pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services

// Every account at a glance, then their combined usage.
ColumnLayout {
    id: root

    property real now: Date.now()

    spacing: Tokens.spacing.medium

    GridLayout {
        Layout.fillWidth: true
        columns: 2
        rowSpacing: Tokens.spacing.medium
        columnSpacing: Tokens.spacing.medium

        Repeater {
            model: AiUsage.accounts

            Card {
                id: card

                required property var modelData
                readonly property color colour: AiUsage.colour(modelData.id)

                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                interactive: true
                stateColour: colour
                onClicked: AiUsage.tab = modelData.id

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.small

                    ProviderLogo {
                        provider: card.modelData.provider
                        colour: card.colour
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        StyledText {
                            Layout.fillWidth: true
                            text: card.modelData.providerName
                            font: Tokens.font.title.small
                            elide: Text.ElideRight
                        }

                        StyledText {
                            Layout.fillWidth: true
                            text: card.modelData.label
                            font: Tokens.font.label.small
                            color: Colours.palette.m3onSurfaceVariant
                            elide: Text.ElideRight
                        }
                    }

                    Chip {
                        visible: !!card.modelData.plan
                        text: card.modelData.plan ?? ""
                        accent: card.colour
                    }
                }

                Repeater {
                    model: card.modelData.limits ?? []

                    LimitCard {
                        required property var modelData

                        Layout.fillWidth: true
                        limit: modelData
                        colour: card.colour
                        now: root.now
                        compact: true
                    }
                }

                StyledText {
                    visible: !card.modelData.available
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: Tr.tr("No limits yet")
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }
        }
    }

    UsageSection {
        Layout.fillWidth: true
        usage: AiUsage.usage
        accounts: AiUsage.accounts
    }
}
