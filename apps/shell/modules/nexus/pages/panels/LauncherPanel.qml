pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.modules.nexus.common

PageBase {
    id: root

    title: Tr.tr("Launcher")
    isSubPage: true

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        // General
        SectionHeader {
            first: true
            text: Tr.tr("General")
        }

        ToggleRow {
            first: true
            last: true
            text: Tr.trCtx("Enabled", "toggle label")
            checked: Config.launcher.enabled
            onToggled: GlobalConfig.launcher.enabled = checked
        }

        // Display
        SectionHeader {
            text: Tr.tr("Display")
        }

        StepperRow {
            first: true
            last: true
            label: Tr.tr("Application suggestions")
            value: Config.launcher.maxShown
            from: 1
            to: 20
            stepSize: 1
            onMoved: v => GlobalConfig.launcher.maxShown = v
        }
    }
}
