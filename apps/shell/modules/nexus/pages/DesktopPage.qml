pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Config
import Wysun.I18n
import qs.modules.nexus.common
import qs.services
import "DesktopSections.js" as DesktopSections

PageBase {
    id: root

    title: "Wysun Settings"

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        Repeater {
            model: DesktopSections.sections

            RowButton {
                required property var modelData
                required property int index

                first: index === 0
                last: index === DesktopSections.sections.length - 1
                icon: modelData.icon
                text: modelData.title
                subtext: modelData.description
                trailingIcon: "open_in_new"
                activeFocusOnTab: true
                color: activeFocus ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
                Keys.onReturnPressed: Quickshell.execDetached(DesktopSections.command(modelData.route))
                Keys.onEnterPressed: Quickshell.execDetached(DesktopSections.command(modelData.route))
                Keys.onSpacePressed: Quickshell.execDetached(DesktopSections.command(modelData.route))
                onClicked: Quickshell.execDetached(DesktopSections.command(modelData.route))
            }
        }
    }
}
