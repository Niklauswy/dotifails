import QtQuick
import QtQuick.Layouts
import Wysun.Config
import qs.components
import qs.services

Item {
    id: root

    required property Props props
    required property ScreenState screenState

    focus: true
    Component.onCompleted: forceActiveFocus()
    Keys.onEscapePressed: root.screenState.sidebar = false

    Connections {
        target: root.screenState
        function onSidebarChanged(): void {
            if (root.screenState.sidebar)
                root.forceActiveFocus();
        }
    }

    ColumnLayout {
        id: layout

        anchors.fill: parent
        spacing: Tokens.spacing.medium

        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true

            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainerLow

            NotifDock {
                objectName: "sidebarNotifications"

                props: root.props
                screenState: root.screenState
            }
        }

        StyledRect {
            Layout.topMargin: Tokens.padding.large - layout.spacing
            Layout.fillWidth: true
            implicitHeight: 1

            color: Colours.tPalette.m3outlineVariant
        }
    }
}
