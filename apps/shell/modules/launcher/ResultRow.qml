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
    height: header ? 30 * panel.scale
        : card ? Tokens.sizes.launcher.itemHeight * 1.7 * panel.scale
        : 40 * panel.scale

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
        anchors.leftMargin: Tokens.padding.small + Tokens.padding.extraSmall
        anchors.bottomMargin: Tokens.padding.extraSmall
        text: root.modelData.title ?? ""
        font: root.panel.fontStrong
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
                font: root.panel.fontBody
                color: Colours.palette.m3onSurfaceVariant
            }
            StyledText {
                text: root.modelData.title ?? ""
                font: Tokens.font.headline.large
                color: Colours.palette.m3onSurface
            }
        }

        StyledText {
            anchors.right: parent.right
            anchors.rightMargin: Tokens.padding.large
            anchors.verticalCenter: parent.verticalCenter
            text: "Copy ↵"
            font: root.panel.fontStrong
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

            readonly property bool appLike: root.modelData.kind === "app" || root.modelData.kind === "window" || root.modelData.kind === "openwith"

            anchors.left: parent.left
            anchors.leftMargin: Tokens.padding.small
            anchors.verticalCenter: parent.verticalCenter
            width: 20 * root.panel.scale
            height: width

            AppIcon {
                anchors.fill: parent
                visible: iconBox.appLike
                name: visible ? (root.modelData.icon ?? "") : ""
                size: parent.width
            }
            Image {
                anchors.fill: parent
                visible: !!root.modelData.thumb
                source: visible ? "file://" + root.modelData.thumb : ""
                sourceSize: Qt.size(64, 64)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }
            Rectangle {
                anchors.fill: parent
                visible: !!root.modelData.swatch
                radius: Tokens.rounding.extraSmall
                color: root.modelData.swatch || "transparent" // theme-exception: user colour sample from clipboard
            }
            MaterialIcon {
                anchors.centerIn: parent
                visible: !iconBox.appLike && !root.modelData.thumb && !root.modelData.swatch
                text: root.modelData.icon || "draft"
                color: Colours.palette.m3onSurface
                fontStyle: Tokens.font.icon.builders.small.scale(root.panel.scale * 1.1).build()
            }
        }

        Row {
            anchors.left: iconBox.right
            anchors.leftMargin: Tokens.spacing.medium
            anchors.right: meta.left
            anchors.rightMargin: Tokens.spacing.medium
            anchors.verticalCenter: parent.verticalCenter
            spacing: Tokens.spacing.small

            StyledText {
                id: title

                text: root.modelData.title ?? ""
                font: root.panel.fontBody
                elide: Text.ElideRight
                width: Math.min(implicitWidth, parent.width)
            }
            StyledText {
                width: Math.max(0, parent.width - title.width - parent.spacing)
                visible: width > 20
                text: root.panel.confirmKey === root.modelData.key ? "Press ↵ again to confirm" : (root.panel.previewOn ? "" : root.modelData.subtitle ?? "")
                font: root.panel.fontBody
                color: root.panel.confirmKey === root.modelData.key ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
                elide: Text.ElideRight
            }
        }

        Row {
            id: meta

            anchors.right: parent.right
            anchors.rightMargin: Tokens.padding.small
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
                visible: !root.panel.previewOn && !(root.panel.ctrlHeld && root.ordinal >= 0 && root.ordinal < 9)
                text: root.modelData.type ?? ""
                font: root.panel.fontBody
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
