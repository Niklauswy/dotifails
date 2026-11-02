pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// Size of the provider's folder by part, with ideas to free space. Wysun only measures; it never deletes.
ColumnLayout {
    id: root

    required property var account

    signal backRequested

    readonly property var disk: account.disk
    readonly property real largest: Math.max(1, ...(disk?.parts ?? []).map(p => p.size))
    readonly property string folder: (disk?.root ?? "").replace(/^~/, Quickshell.env("HOME"))

    function tipText(kind: string): string {
        if (kind === "old-logs")
            return Tr.tr("Session logs older than 90 days");
        if (kind === "file-history")
            return Tr.tr("Copies of files edited in sessions");
        return kind;
    }

    spacing: Tokens.spacing.small

    PageHeader {
        title: Tr.tr("Disk space · %1").arg(root.account.providerName)
        onBackRequested: root.backRequested()

        Chip {
            text: Format.bytes(root.disk?.total ?? 0)
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small

        StyledText {
            Layout.fillWidth: true
            text: root.disk?.root ?? ""
            font: Tokens.font.mono.small
        }

        StyledText {
            // TRANSLATORS: %1 = time such as "Mon 14:00"
            text: Tr.tr("measured %1 · once a day").arg(Qt.formatDateTime(new Date((root.disk?.measuredAt ?? 0) * 1000), "ddd hh:mm"))
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    Repeater {
        model: root.disk?.parts ?? []

        RowLayout {
            id: part

            required property var modelData

            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.rightMargin: Tokens.padding.small
            spacing: Tokens.spacing.medium

            StyledText {
                Layout.fillWidth: true
                text: part.modelData.name
                font: Tokens.font.mono.small
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
                    width: parent.width * part.modelData.size / root.largest
                    radius: Tokens.rounding.full
                    color: Colours.palette.m3primary
                }
            }

            StyledText {
                Layout.preferredWidth: Tokens.spacing.extraExtraLarge + Tokens.spacing.medium
                horizontalAlignment: Text.AlignRight
                text: Format.bytes(part.modelData.size)
                font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
            }
        }
    }

    Divider {
        Layout.topMargin: Tokens.spacing.small
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        Layout.rightMargin: Tokens.padding.small
        Layout.topMargin: Tokens.spacing.small

        StyledText {
            Layout.fillWidth: true
            text: Tr.tr("Ideas to free space")
            font: Tokens.font.label.builders.medium.weight(Font.DemiBold).build()
            color: Colours.palette.m3onSurfaceVariant
        }

        StyledText {
            text: Tr.tr("Wysun never deletes anything")
            font: Tokens.font.label.small
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    StyledText {
        visible: !(root.disk?.tips ?? []).length
        Layout.leftMargin: Tokens.padding.small
        text: Tr.tr("Nothing worth cleaning.")
        font: Tokens.font.label.small
        color: Colours.palette.m3onSurfaceVariant
    }

    Repeater {
        model: root.disk?.tips ?? []

        MenuRow {
            required property var modelData

            icon: "lightbulb"
            text: root.tipText(modelData.kind)
            detail: Format.bytes(modelData.size)
            enabled: false
        }
    }

    Divider {}

    MenuRow {
        icon: "folder_open"
        text: Tr.tr("Open folder")
        detail: root.disk?.root ?? ""
        trailing: "open_in_new"
        onClicked: Quickshell.execDetached(["xdg-open", root.folder])
    }
}
