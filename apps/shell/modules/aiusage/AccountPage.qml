pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// One signed-in account: identity and plan, its limits and its own usage.
ColumnLayout {
    id: root

    required property var account
    property real now: Date.now()

    readonly property color colour: AiUsage.colour(account.id)
    readonly property string age: Format.age(account.updatedAt, now)
    readonly property int resetCredits: account.resetCredits?.available ?? 0

    spacing: Tokens.spacing.medium

    Card {
        Layout.fillWidth: true

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.medium

            StyledRect {
                implicitWidth: Tokens.sizes.aiUsage.limitBarHeight * 2
                implicitHeight: implicitWidth
                radius: Tokens.rounding.full
                color: Qt.alpha(root.colour, 0.18)

                ProviderLogo {
                    anchors.centerIn: parent
                    provider: root.account.provider
                    colour: root.colour
                    size: Tokens.spacing.extraLarge
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                RowLayout {
                    spacing: Tokens.spacing.small

                    StyledText {
                        text: root.account.providerName
                        font: Tokens.font.title.medium
                    }

                    Chip {
                        visible: !!root.account.plan
                        text: root.account.plan ?? ""
                        accent: root.colour
                    }

                    Chip {
                        visible: root.resetCredits > 0
                        // TRANSLATORS: %1 = number of Codex rate-limit reset credits
                        text: Tr.tr("%1 resets").arg(root.resetCredits)
                        accent: Colours.palette.m3tertiary
                    }
                }

                StyledText {
                    Layout.fillWidth: true
                    text: root.account.email || root.account.label
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                    elide: Text.ElideMiddle
                }

                StyledText {
                    Layout.fillWidth: true
                    text: {
                        const source = root.account.source === "app-server" ? Tr.tr("live from Codex") : root.account.source === "statusline" ? Tr.tr("from Claude Code") : root.account.source === "history" ? Tr.tr("not signed in, from session history") : Tr.tr("from session logs");
                        // TRANSLATORS: %1 = elapsed time such as "5m", %2 = where the limits came from
                        return root.age ? Tr.tr("Updated %1 ago · %2").arg(root.age).arg(source) : Tr.tr("Updated just now · %1").arg(source);
                    }
                    font: Tokens.font.label.small
                    color: Colours.palette.m3outline
                    elide: Text.ElideRight
                }
            }
        }
    }

    Card {
        Layout.fillWidth: true
        visible: !root.account.available

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: "info"
                color: Colours.palette.m3primary
                fontStyle: Tokens.font.icon.medium
            }

            StyledText {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: root.account.reason === "statusline" ? Tr.tr("Limits appear after Claude Code refreshes its status line once.") : root.account.reason === "cli" ? Tr.tr("Codex CLI not found in PATH.") : root.account.reason === "history" ? Tr.tr("This account is not signed in; only its usage history is shown.") : Tr.tr("No limits reported yet.")
                font: Tokens.font.body.small
                color: Colours.palette.m3onSurfaceVariant
            }
        }
    }

    Repeater {
        model: root.account.limits ?? []

        Card {
            id: limitCard

            required property var modelData

            Layout.fillWidth: true

            LimitCard {
                Layout.fillWidth: true
                limit: limitCard.modelData
                colour: root.colour
                now: root.now
                resetCredits: root.resetCredits
            }
        }
    }

    // Banked resets are only shown; redeeming them stays in the provider's own tools.
    Card {
        Layout.fillWidth: true
        visible: root.resetCredits > 0

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: "confirmation_number"
                color: Colours.palette.m3tertiary
                fontStyle: Tokens.font.icon.medium
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    // TRANSLATORS: %1 = number of banked rate-limit resets
                    text: Tr.tr("%1 banked").arg(root.resetCredits)
                    font: Tokens.font.title.small
                }

                Repeater {
                    model: root.account.resetCredits?.credits ?? []

                    StyledText {
                        required property var modelData

                        Layout.fillWidth: true
                        text: (modelData.title || Tr.tr("Reset")) + (modelData.expiresAt ? " · " + Tr.tr("expires in %1").arg(Format.countdown(modelData.expiresAt, root.now)) : "")
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSurfaceVariant
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }

    UsageSection {
        Layout.fillWidth: true
        usage: root.account.usage
        accounts: [root.account]
    }
}
