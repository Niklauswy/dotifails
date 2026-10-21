import QtQuick
import Wysun.Config
import qs.components
import qs.services
import qs.modules.launcher.services

Item {
    id: root

    required property var modelData
    required property var list

    function onClicked(): void {
        if (LauncherData.activate(modelData))
            list.screenState.launcher = false;
    }

    implicitHeight: Tokens.sizes.launcher.itemHeight

    anchors.left: parent?.left
    anchors.right: parent?.right

    StateLayer {
        radius: Tokens.rounding.large
        onClicked: root.onClicked()
    }

    Item {
        anchors.fill: parent
        anchors.leftMargin: Tokens.padding.medium
        anchors.rightMargin: Tokens.padding.medium
        anchors.margins: Tokens.padding.small

        Item {
            id: iconBox

            implicitWidth: icon.implicitWidth
            implicitHeight: icon.implicitHeight
            anchors.verticalCenter: parent.verticalCenter

            MaterialIcon {
                id: icon

                visible: !(root.modelData?.swatch)
                text: root.modelData?.icon || "help_outline"
                color: root.modelData?.kind === "error" ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.builders.large.scale(1.3).build()
            }

            // theme-exception: the swatch shows the user's own clipboard colour
            Rectangle {
                anchors.centerIn: parent
                visible: !!root.modelData?.swatch
                width: icon.implicitWidth * 0.8
                height: width
                radius: width / 2
                color: root.modelData?.swatch || "transparent"
                border.width: 1
                border.color: Colours.palette.m3outline
            }
        }

        Item {
            anchors.left: iconBox.right
            anchors.leftMargin: Tokens.spacing.medium
            anchors.verticalCenter: iconBox.verticalCenter

            implicitWidth: parent.width - iconBox.width
            implicitHeight: name.implicitHeight + desc.implicitHeight

            StyledText {
                id: name

                text: root.modelData?.title ?? ""
                font: Tokens.font.body.medium
                elide: Text.ElideRight
                width: root.width - iconBox.width - Tokens.rounding.extraLargeIncreased
            }

            StyledText {
                id: desc

                text: root.modelData?.subtitle ?? ""
                font: Tokens.font.body.small
                color: Colours.palette.m3outline
                elide: Text.ElideRight
                width: root.width - iconBox.width - Tokens.rounding.extraLargeIncreased
                anchors.top: name.bottom
            }
        }
    }
}
