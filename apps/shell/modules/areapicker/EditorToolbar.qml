pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.effects
import qs.services

// Floating toolbar of the annotation editor.
StyledRect {
    id: root

    required property Annotations annotations
    // Drawing over a recording instead of a capture: no pixelate, no copy or save, but clear and done.
    property bool live

    // Theme swatches for marks; they follow the active scheme.
    readonly property var swatches: [Colours.palette.m3error, Colours.palette.m3primary, Colours.palette.m3tertiary, Colours.palette.m3secondary, Colours.palette.m3onSurface, Colours.palette.m3surface]
    readonly property var tools: [
        { id: "pen", icon: "edit", label: Tr.tr("Pen") },
        { id: "marker", icon: "ink_highlighter", label: Tr.tr("Highlighter") },
        { id: "line", icon: "horizontal_rule", label: Tr.tr("Line") },
        { id: "arrow", icon: "arrow_outward", label: Tr.tr("Arrow") },
        { id: "rect", icon: "crop_square", label: Tr.tr("Rectangle") },
        { id: "ellipse", icon: "circle", label: Tr.tr("Ellipse") },
        { id: "text", icon: "title", label: Tr.tr("Text") },
        { id: "counter", icon: "looks_one", label: Tr.tr("Counter") },
        { id: "pixelate", icon: "blur_on", label: Tr.tr("Pixelate") }
    ]

    signal copy
    signal save
    signal cancel
    signal clear

    implicitWidth: row.implicitWidth + Tokens.padding.small * 2
    implicitHeight: row.implicitHeight + Tokens.padding.small * 2
    radius: Tokens.rounding.full
    color: Colours.palette.m3surfaceContainer
    border.width: 1
    border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)

    Elevation {
        anchors.fill: parent
        radius: root.radius
        level: 3
        z: -1
    }

    RowLayout {
        id: row

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall

        Repeater {
            model: root.live ? root.tools.filter(t => t.id !== "pixelate") : root.tools

            Tool {
                required property var modelData
                required property int index

                icon: modelData.icon
                hint: `${modelData.label} · ${index + 1}`
                active: root.annotations.tool === modelData.id
                onClicked: root.annotations.tool = modelData.id
            }
        }

        Separator {}

        Repeater {
            model: root.swatches

            StyledRect {
                id: swatch

                required property color modelData
                readonly property bool active: Qt.colorEqual(root.annotations.colour, modelData)

                implicitWidth: Tokens.spacing.extraLarge
                implicitHeight: implicitWidth
                radius: Tokens.rounding.full
                color: "transparent"
                border.width: active ? 2 : 0
                border.color: Colours.palette.m3onSurface

                StyledRect {
                    anchors.centerIn: parent
                    width: parent.width - Tokens.padding.small
                    height: width
                    radius: Tokens.rounding.full
                    color: swatch.modelData
                    border.width: 1
                    border.color: Qt.alpha(Colours.palette.m3outline, 0.5)
                }

                StateLayer {
                    radius: Tokens.rounding.full
                    onClicked: root.annotations.colour = swatch.modelData
                }
            }
        }

        Separator {}

        Repeater {
            model: 3

            Tool {
                required property int index

                icon: "fiber_manual_record"
                iconScale: [0.55, 0.8, 1.1][index]
                hint: [Tr.tr("Thin"), Tr.tr("Medium"), Tr.tr("Thick")][index]
                active: root.annotations.size === index
                onClicked: root.annotations.size = index
            }
        }

        Separator {}

        Tool {
            icon: "undo"
            hint: Tr.tr("Undo · Ctrl+Z")
            enabled: root.annotations.marks.length > 0
            onClicked: root.annotations.undo()
        }

        Tool {
            icon: "redo"
            hint: Tr.tr("Redo · Ctrl+Shift+Z")
            enabled: root.annotations.undone.length > 0
            onClicked: root.annotations.redo()
        }

        Separator {}

        Tool {
            visible: !root.live
            icon: "save_as"
            hint: Tr.tr("Save as… · Ctrl+S")
            onClicked: root.save()
        }

        Tool {
            visible: root.live
            icon: "delete_sweep"
            hint: Tr.tr("Clear all")
            enabled: root.annotations.marks.length > 0
            onClicked: root.clear()
        }

        StyledRect {
            visible: !root.live
            implicitWidth: copyRow.implicitWidth + Tokens.padding.medium * 2
            implicitHeight: copyRow.implicitHeight + Tokens.padding.small * 2
            radius: Tokens.rounding.full
            color: Colours.palette.m3primary

            StateLayer {
                radius: parent.radius
                color: Colours.palette.m3onPrimary
                onClicked: root.copy()
            }

            RowLayout {
                id: copyRow

                anchors.centerIn: parent
                spacing: Tokens.spacing.small

                MaterialIcon {
                    text: "content_copy"
                    color: Colours.palette.m3onPrimary
                    fontStyle: Tokens.font.icon.medium
                }

                StyledText {
                    text: Tr.tr("Copy")
                    font: Tokens.font.label.builders.large.weight(Font.Medium).build()
                    color: Colours.palette.m3onPrimary
                }
            }
        }

        Tool {
            icon: root.live ? "check" : "close"
            hint: root.live ? Tr.tr("Done · Esc") : Tr.tr("Cancel · Esc")
            onClicked: root.cancel()
        }
    }

    component Separator: StyledRect {
        Layout.preferredWidth: 1
        Layout.preferredHeight: Tokens.spacing.large
        Layout.leftMargin: Tokens.spacing.extraSmall
        Layout.rightMargin: Tokens.spacing.extraSmall
        color: Colours.palette.m3outlineVariant
    }

    component Tool: StyledRect {
        id: tool

        property string icon
        property string hint
        property bool active
        property real iconScale: 1

        signal clicked

        implicitWidth: Tokens.spacing.extraLarge + Tokens.padding.small
        implicitHeight: implicitWidth
        radius: Tokens.rounding.full
        color: active ? Colours.palette.m3secondaryContainer : "transparent"
        opacity: enabled ? 1 : 0.38

        StateLayer {
            id: layer

            radius: tool.radius
            color: tool.active ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
            disabled: !tool.enabled
            onClicked: tool.clicked()
        }

        MaterialIcon {
            anchors.centerIn: parent
            text: tool.icon
            fill: tool.active ? 1 : 0
            color: tool.active ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
            fontStyle: Tokens.font.icon.medium
            scale: tool.iconScale
        }

        // Tooltip with the name and its key.
        StyledRect {
            anchors.bottom: parent.top
            anchors.bottomMargin: Tokens.spacing.small
            anchors.horizontalCenter: parent.horizontalCenter
            visible: layer.containsMouse && tool.hint.length > 0
            implicitWidth: tip.implicitWidth + Tokens.padding.small * 2
            implicitHeight: tip.implicitHeight + Tokens.padding.extraSmall * 2
            radius: Tokens.rounding.small
            color: Colours.palette.m3inverseSurface

            StyledText {
                id: tip

                anchors.centerIn: parent
                text: tool.hint
                font: Tokens.font.label.small
                color: Colours.palette.m3inverseOnSurface
            }
        }
    }
}
