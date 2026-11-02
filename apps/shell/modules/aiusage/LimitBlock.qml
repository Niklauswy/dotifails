import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services
import "Format.js" as Format

// One usage window: used (or left) share, a bar with the even-use mark, reset time and pace.
// Clicking opens its history.
Item {
    id: root

    required property var limit
    property real now: Date.now()
    property bool clickable: true

    readonly property bool showUsed: AiUsage.settings.showUsed
    readonly property real used: limit.usedPercent
    readonly property real shown: showUsed ? used : 100 - used
    readonly property var pace: AiUsage.pace(limit)
    readonly property color fill: AiUsage.severityColour(used)

    signal clicked

    Layout.fillWidth: true
    implicitHeight: layout.implicitHeight + Tokens.padding.medium * 2

    function resetText(): string {
        if (!limit.resetsAt)
            return Tr.tr("No active window");
        if (AiUsage.settings.absoluteResets)
            return Tr.tr("Resets %1").arg(Qt.formatDateTime(new Date(limit.resetsAt * 1000), limit.windowMinutes > 1440 ? "ddd hh:mm" : "hh:mm"));
        return Tr.tr("Resets in %1").arg(Format.countdown(limit.resetsAt, now));
    }

    function windowText(): string {
        const minutes = limit.windowMinutes ?? 0;
        if (minutes >= 43200)
            return Tr.tr("month");
        if (minutes >= 10080)
            return Tr.tr("7 days");
        if (minutes >= 1440)
            return Tr.tr("day");
        return Tr.tr("%1 h").arg(Math.round(minutes / 60));
    }

    StateLayer {
        visible: root.clickable
        radius: Tokens.rounding.large
        color: Colours.palette.m3onSurface
        onClicked: root.clicked()
    }

    ColumnLayout {
        id: layout

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Tokens.padding.small
        anchors.rightMargin: Tokens.padding.small
        spacing: Tokens.spacing.small

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            StyledText {
                text: AiUsage.limitTitle(root.limit)
                font: Tokens.font.title.small
            }

            StyledText {
                Layout.alignment: Qt.AlignBaseline
                text: root.windowText()
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }

            Item {
                Layout.fillWidth: true
            }

            StyledText {
                // TRANSLATORS: %1 = percent; "used" or "left" of a usage limit
                text: (root.showUsed ? Tr.tr("%1% used") : Tr.tr("%1% left")).arg(Math.round(root.shown))
                font: Tokens.font.title.builders.small.weight(Font.DemiBold).build()
                color: root.used >= 90 ? Colours.palette.m3error : Colours.palette.m3onSurface
            }

            MaterialIcon {
                visible: root.clickable
                text: "chevron_right"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }
        }

        // Track, fill and the even-use mark.
        Item {
            Layout.fillWidth: true
            implicitHeight: Tokens.spacing.small

            StyledRect {
                anchors.fill: parent
                radius: Tokens.rounding.full
                color: Qt.alpha(Colours.palette.m3onSurface, 0.09)
            }

            StyledRect {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * Math.max(0, Math.min(1, root.shown / 100))
                radius: Tokens.rounding.full
                color: root.fill

                Behavior on width {
                    Anim {}
                }
            }

            Rectangle {
                visible: AiUsage.settings.paceGuide && !!root.pace && !root.pace.early && !root.pace.exhausted
                x: parent.width * ((root.showUsed ? root.pace?.expected ?? 0 : 100 - (root.pace?.expected ?? 0)) / 100) - width / 2
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 2
                implicitHeight: parent.height + Tokens.spacing.small
                radius: 1
                color: Qt.alpha(Colours.palette.m3onSurface, 0.6)
            }
        }

        RowLayout {
            Layout.fillWidth: true

            StyledText {
                text: (root.showUsed ? Tr.tr("%1% left") : Tr.tr("%1% used")).arg(Math.round(100 - root.shown))
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }

            Item {
                Layout.fillWidth: true
            }

            StyledText {
                text: root.resetText()
                font: Tokens.font.label.small
                color: Colours.palette.m3onSurfaceVariant
            }
        }

        RowLayout {
            visible: !!root.pace && !root.pace.early
            spacing: Tokens.spacing.small

            Chip {
                readonly property int delta: root.pace?.delta ?? 0

                text: root.pace?.exhausted ? Tr.tr("Exhausted") : Math.abs(delta) < 5 ? Tr.tr("On pace") : delta > 0 ? Tr.tr("%1% in deficit").arg(delta) : Tr.tr("%1% in reserve").arg(-delta)
                accent: root.pace?.exhausted || delta >= 5 ? Colours.palette.m3error : delta <= -5 ? Colours.palette.m3success : Colours.palette.m3onSurfaceVariant
            }

            StyledText {
                text: root.pace?.exhausted ? Tr.tr("until the reset") : root.pace?.lasts ? Tr.tr("Lasts until reset") : Tr.tr("Runs out in %1").arg(Format.countdown(root.now / 1000 + (root.pace?.runsOutIn ?? 0), root.now))
                font: Tokens.font.label.small
                color: root.pace && !root.pace.lasts ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
            }
        }
    }
}
