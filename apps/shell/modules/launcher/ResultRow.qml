pragma ComponentBehavior: Bound

import QtQuick
import Wysun.Config
import qs.components
import qs.services

// One list entry: a section header, a calculator card or a regular result row.
Item {
    id: root

    required property var modelData
    required property int index
    required property var panel

    readonly property bool header: modelData.header === true
    readonly property bool card: modelData.kind === "calc"
    readonly property bool current: panel.selected === index
    readonly property int ordinal: modelData.n ?? -1

    width: ListView.view?.width ?? 0
    height: header ? Tokens.sizes.launcher.itemHeight * 0.5 * panel.scale + Tokens.padding.small
        : card ? Tokens.sizes.launcher.itemHeight * 1.7 * panel.scale
        : Tokens.sizes.launcher.itemHeight * 0.88 * panel.scale

    function report(): void {
        if (current && !header) {
            panel.hlY = y;
            panel.hlH = height;
            panel.hlOn = true;
        }
    }

    onCurrentChanged: report()
    onYChanged: report()
    onHeightChanged: report()
    Component.onCompleted: report()
    ListView.onReused: report()

    StyledText {
        visible: root.header
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: Tokens.padding.large
        anchors.bottomMargin: Tokens.padding.extraSmall
        text: root.modelData.title ?? ""
        font: Tokens.font.label.medium
        color: Colours.palette.m3onSurfaceVariant
    }

    // Calculator card
    Item {
        visible: root.card
        anchors.fill: parent
        anchors.margins: Tokens.padding.extraSmall

        Column {
            anchors.left: parent.left
            anchors.leftMargin: Tokens.padding.large
            anchors.verticalCenter: parent.verticalCenter
            spacing: Tokens.spacing.extraSmall

            StyledText {
                text: root.modelData.subtitle ?? ""
                font: Tokens.font.body.medium
                color: Colours.palette.m3onSecondaryContainer
                opacity: 0.7
            }
            StyledText {
                text: root.modelData.title ?? ""
                font: Tokens.font.headline.large
                color: Colours.palette.m3onSecondaryContainer
            }
        }

        StyledText {
            anchors.right: parent.right
            anchors.rightMargin: Tokens.padding.large
            anchors.verticalCenter: parent.verticalCenter
            text: "Copy ↵"
            font: Tokens.font.label.medium
            color: Colours.palette.m3onSurfaceVariant
        }
    }

    // Regular row
    Item {
        visible: !root.header && !root.card
        anchors.fill: parent
        anchors.leftMargin: Tokens.padding.small
        anchors.rightMargin: Tokens.padding.small

        Item {
            id: iconBox

            anchors.left: parent.left
            anchors.leftMargin: Tokens.padding.small
            anchors.verticalCenter: parent.verticalCenter
            width: 32 * root.panel.scale
            height: width

            AppIcon {
                anchors.fill: parent
                visible: root.modelData.kind === "app" || root.modelData.kind === "window" || root.modelData.kind === "openwith"
                name: visible ? (root.modelData.icon ?? "") : ""
                size: parent.width
            }
            Rectangle {
                anchors.fill: parent
                visible: root.modelData.swatch !== undefined && root.modelData.swatch !== ""
                radius: Tokens.rounding.small
                color: root.modelData.swatch || "transparent" // theme-exception: user colour sample from clipboard
            }
            Rectangle {
                anchors.fill: parent
                visible: !(root.modelData.kind === "app" || root.modelData.kind === "window" || root.modelData.kind === "openwith") && !(root.modelData.swatch)
                radius: Tokens.rounding.small
                color: root.current ? Colours.palette.m3primaryContainer : Colours.tPalette.m3surfaceContainerHigh

                MaterialIcon {
                    anchors.centerIn: parent
                    text: root.modelData.icon || "draft"
                    color: root.current ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3primary
                    fontStyle: Tokens.font.icon.builders.medium.scale(root.panel.scale).build()
                }
            }
        }

        Column {
            anchors.left: iconBox.right
            anchors.leftMargin: Tokens.spacing.medium
            anchors.right: meta.left
            anchors.rightMargin: Tokens.spacing.medium
            anchors.verticalCenter: parent.verticalCenter

            StyledText {
                width: parent.width
                text: root.modelData.title ?? ""
                font: Tokens.font.body.medium
                elide: Text.ElideRight
            }
            StyledText {
                width: parent.width
                text: root.panel.confirmKey === root.modelData.key ? "Press ↵ again to confirm" : (root.modelData.subtitle ?? "")
                font: Tokens.font.body.small
                color: root.panel.confirmKey === root.modelData.key ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
                elide: Text.ElideRight
                visible: text !== ""
            }
        }

        Row {
            id: meta

            anchors.right: parent.right
            anchors.rightMargin: Tokens.padding.medium
            anchors.verticalCenter: parent.verticalCenter
            spacing: Tokens.spacing.small

            MaterialIcon {
                visible: root.modelData.pinned === true
                anchors.verticalCenter: parent.verticalCenter
                text: "keep"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }
            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                visible: !(root.panel.ctrlHeld && root.ordinal >= 0 && root.ordinal < 9)
                text: root.modelData.type ?? ""
                font: Tokens.font.label.medium
                color: Colours.palette.m3onSurfaceVariant
            }
            Keycaps {
                anchors.verticalCenter: parent.verticalCenter
                visible: root.panel.ctrlHeld && root.ordinal >= 0 && root.ordinal < 9
                keys: ["Ctrl", String(root.ordinal + 1)]
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: !root.header
        hoverEnabled: true
        // Only a real pointer movement selects; rows sliding under a still pointer must not steal it.
        onPositionChanged: mouse => {
            const p = mapToItem(null, mouse.x, mouse.y);
            const first = root.panel.pointerX < 0;
            if (!first && Math.abs(p.x - root.panel.pointerX) + Math.abs(p.y - root.panel.pointerY) < 2)
                return;
            root.panel.pointerX = p.x;
            root.panel.pointerY = p.y;
            if (!first && root.panel.selected !== root.index)
                root.panel.select(root.index);
        }
        onClicked: root.panel.activate(root.modelData)
    }
}
