pragma ComponentBehavior: Bound

import QtQuick
import M3Shapes
import Wysun.Config
import qs.components
import qs.services
import "services/Colour.js" as Colour

// One list entry: a section header, a calculator card or a regular result row. Rows replay a
// short staggered entrance whenever the panel opens or changes view (panel.entrance).
Item {
    id: root

    required property var modelData
    required property int index
    required property var panel

    readonly property bool header: modelData.header === true
    readonly property bool card: modelData.kind === "calc"
    readonly property bool current: panel.selected === index
    readonly property int ordinal: modelData.n ?? -1
    readonly property string subtitleText: panel.confirmKey === modelData.key ? "Press ↵ again to confirm" : (modelData.subtitle ?? "")

    width: ListView.view?.width ?? 0
    height: header ? 32 * panel.scale
        : card ? 92 * panel.scale
        : 54 * panel.scale

    Component.onCompleted: enter()

    // Staggered entrance: only the first rows on screen, so long lists cost nothing extra.
    property real enterProgress: 1

    function enter(): void {
        if (index < 0 || index > 12)
            return;
        enterProgress = 0;
        entranceAnim.restart();
    }

    Connections {
        target: root.panel

        function onEntranceChanged(): void {
            root.enter();
        }
    }

    SequentialAnimation {
        id: entranceAnim

        PauseAnimation {
            duration: Math.max(0, root.index) * 18
        }
        Anim {
            target: root
            property: "enterProgress"
            to: 1
            type: Anim.DefaultSpatial
        }
    }

    opacity: Math.min(1, enterProgress * 1.4)
    transform: Translate {
        y: (1 - root.enterProgress) * 10 * root.panel.scale
    }

    StyledText {
        visible: root.header
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: Tokens.padding.medium
        anchors.bottomMargin: Tokens.padding.extraSmall + 2
        text: root.modelData.title ?? ""
        font: Tokens.font.body.builders.small.size(9 * root.panel.scale).weight(Font.DemiBold).build()
        color: Colours.palette.m3primary
    }

    // Calculator card: the result large, on a tertiary container.
    Rectangle {
        visible: root.card
        anchors.fill: parent
        anchors.topMargin: Tokens.padding.extraSmall
        anchors.bottomMargin: Tokens.padding.extraSmall
        radius: Tokens.rounding.large
        color: Colours.palette.m3tertiaryContainer

        Column {
            anchors.left: parent.left
            anchors.leftMargin: Tokens.padding.large
            anchors.verticalCenter: parent.verticalCenter
            spacing: Tokens.spacing.extraSmall

            StyledText {
                text: root.modelData.subtitle ?? ""
                font: root.panel.fontBody
                color: Colours.palette.m3onTertiaryContainer
                opacity: 0.8
            }
            StyledText {
                text: root.modelData.title ?? ""
                font: Tokens.font.headline.large
                color: Colours.palette.m3onTertiaryContainer
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: Tokens.padding.large
            anchors.verticalCenter: parent.verticalCenter
            spacing: Tokens.spacing.small

            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                text: "Copy"
                font: root.panel.fontStrong
                color: Colours.palette.m3onTertiaryContainer
            }
            Keycaps {
                anchors.verticalCenter: parent.verticalCenter
                keys: ["↵"]
            }
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

            readonly property bool appLike: root.modelData.kind === "app" || root.modelData.kind === "openwith"
            readonly property bool picture: !!root.modelData.thumb || !!root.modelData.swatch

            anchors.left: parent.left
            anchors.leftMargin: Tokens.padding.small
            anchors.verticalCenter: parent.verticalCenter
            width: 36 * root.panel.scale
            height: width

            // The container morphs from a circle to a cookie on selection (apps only show it then).
            MaterialShape {
                anchors.centerIn: parent
                implicitSize: parent.width
                visible: !iconBox.picture
                shape: root.current ? MaterialShape.Cookie9Sided : MaterialShape.Circle
                color: root.current ? Colours.palette.m3primaryContainer : Colours.palette.m3surfaceContainerHighest
                opacity: iconBox.appLike && !root.current ? 0 : 1
                scale: iconBox.appLike && !root.current ? 0.6 : 1
                animationEasing: Tokens.anim.expressiveFastSpatial
                animationDuration: Tokens.anim.durations.expressiveFastSpatial

                Behavior on color {
                    CAnim {}
                }
                Behavior on opacity {
                    Anim {
                        type: Anim.FastEffects
                    }
                }
                Behavior on scale {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
            }
            AppIcon {
                anchors.centerIn: parent
                width: parent.width * (root.current ? 0.66 : 0.84)
                height: width
                visible: iconBox.appLike
                name: visible ? (root.modelData.icon ?? "") : ""
                size: parent.width

                Behavior on width {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
            }
            ClipRect {
                anchors.fill: parent
                visible: !!root.modelData.thumb
                radius: Tokens.rounding.small

                Image {
                    anchors.fill: parent
                    source: parent.visible ? "file://" + root.modelData.thumb : ""
                    sourceSize: Qt.size(96, 96)
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                }
            }
            Rectangle {
                anchors.fill: parent
                visible: !!root.modelData.swatch
                radius: root.current ? Tokens.rounding.medium : width / 2
                color: root.modelData.swatch ? Colour.parse(root.modelData.swatch) : "transparent" // theme-exception: user colour sample from clipboard
                border.width: 1
                border.color: Colours.palette.m3outlineVariant

                Behavior on radius {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
            }
            MaterialIcon {
                anchors.centerIn: parent
                visible: !iconBox.appLike && !iconBox.picture
                text: root.modelData.icon || "draft"
                fill: root.current ? 1 : 0
                color: root.current ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.builders.small.scale(root.panel.scale * 1.1).build()
            }
        }

        Column {
            anchors.left: iconBox.right
            anchors.leftMargin: Tokens.spacing.medium + 2
            anchors.right: meta.left
            anchors.rightMargin: Tokens.spacing.medium
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1

            StyledText {
                width: parent.width
                text: root.modelData.title ?? ""
                font: root.current ? Tokens.font.body.builders.medium.size(10.5 * root.panel.scale).weight(Font.DemiBold).build() : root.panel.fontBody
                color: root.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                elide: Text.ElideRight
            }
            StyledText {
                width: parent.width
                visible: text !== ""
                text: root.subtitleText
                font: root.panel.fontSmall
                color: root.panel.confirmKey === root.modelData.key ? Colours.palette.m3error : root.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                opacity: root.current ? 0.85 : 1
                elide: root.modelData.kind === "file" ? Text.ElideMiddle : Text.ElideRight
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
                fill: 1
                color: Colours.palette.m3primary
                fontStyle: Tokens.font.icon.small
            }
            // Kind as a quiet tonal chip; it steps aside for the Ctrl+number hints.
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                visible: !root.panel.previewOn && !!root.modelData.type && !(root.panel.ctrlHeld && root.ordinal >= 0 && root.ordinal < 9)
                width: typeLabel.implicitWidth + Tokens.padding.medium * 1.5
                height: 22 * root.panel.scale
                radius: height / 2
                color: root.current ? Qt.alpha(Colours.palette.m3onSecondaryContainer, 0.12) : Colours.palette.m3surfaceContainerHigh

                StyledText {
                    id: typeLabel

                    anchors.centerIn: parent
                    text: root.modelData.type ?? ""
                    font: root.panel.fontSmall
                    color: root.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                }
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
        cursorShape: Qt.PointingHandCursor
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
