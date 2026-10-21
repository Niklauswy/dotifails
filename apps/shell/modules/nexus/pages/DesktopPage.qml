pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services
import qs.modules.nexus.common
import "DesktopSections.js" as DesktopSections

// Desktop section hub: every setting that used to live in the Qt Wysun Settings window.
PageBase {
    id: root

    title: "Escritorio"

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        Repeater {
            model: DesktopSections.sections

            NavRow {
                required property var modelData
                required property int index

                first: index === 0
                last: index === DesktopSections.sections.length - 1
                icon: modelData.icon
                text: modelData.title
                subtext: modelData.description
                activeFocusOnTab: true
                Keys.onReturnPressed: root.nState.openDesktopSection(modelData)
                Keys.onEnterPressed: root.nState.openDesktopSection(modelData)
                Keys.onSpacePressed: root.nState.openDesktopSection(modelData)
                onClicked: root.nState.openDesktopSection(modelData)
            }
        }
    }
}
