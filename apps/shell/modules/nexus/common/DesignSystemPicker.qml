pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import M3Shapes
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.services

// Settings → Wallpaper & style → Design system.
// Wysun is built on Material Design 3 (Expressive): it is the only design system and is always selected.
// Fluent 2 is planned: its card is shown disabled with a WIP chip and nothing is persisted for it
// (theme.json keeps only {"mode": ...}; see docs/themes.md, "Sistema de diseño").
// Both previews paint the live wallpaper palette; Fluent's acrylic and mica are derived from the same roles.
GridLayout {
    id: root

    // The only design system Wysun ships today; read by tests and future persistence.
    readonly property string current: "material"
    // Two columns when two cards fit side by side, stacked otherwise.
    readonly property bool sideBySide: width >= Tokens.sizes.nexus.popupWidth * 2 + columnSpacing

    Layout.fillWidth: true
    columns: sideBySide ? 2 : 1
    columnSpacing: Tokens.spacing.medium
    rowSpacing: Tokens.spacing.medium

    DesignCard {
        system: "material"
        name: Tr.tr("Material Design 3")
        description: Tr.tr("Colours from your wallpaper, expressive shapes")
        wip: false
        preview: materialPreview
    }

    DesignCard {
        system: "fluent"
        name: Tr.tr("Fluent 2")
        description: Tr.tr("Coming soon")
        wip: true
        preview: fluentPreview
    }

    // Material 3 Expressive: a morphing shape, a pill button and a FAB on the wallpaper scheme.
    Component {
        id: materialPreview

        StyledRect {
            id: canvas

            property bool active
            readonly property real unit: height / 6

            color: Colours.palette.m3surface
            radius: Tokens.rounding.large

            MaterialShape {
                id: heroShape

                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: Tokens.padding.medium
                implicitSize: canvas.unit * 2
                shape: MaterialShape.Cookie9Sided
                color: Colours.palette.m3primaryContainer

                MaterialIcon {
                    anchors.centerIn: parent
                    text: "palette"
                    fill: 1
                    color: Colours.palette.m3onPrimaryContainer
                    fontStyle: Tokens.font.icon.small
                }

                // Hovering the card turns the shape, an expressive spatial spring.
                rotation: canvas.active ? 90 : 0

                Behavior on rotation {
                    Anim {
                        type: Anim.SlowSpatial
                    }
                }
            }

            Column {
                anchors.left: heroShape.right
                anchors.right: parent.right
                anchors.verticalCenter: heroShape.verticalCenter
                anchors.leftMargin: Tokens.spacing.medium
                anchors.rightMargin: Tokens.padding.medium
                spacing: Tokens.spacing.small

                StyledRect {
                    width: parent.width * 0.7
                    height: Tokens.padding.small
                    radius: Tokens.rounding.full
                    color: Colours.palette.m3onSurface
                }

                StyledRect {
                    width: parent.width * 0.45
                    height: Tokens.padding.small
                    radius: Tokens.rounding.full
                    color: Colours.palette.m3outlineVariant
                }
            }

            StyledRect {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.margins: Tokens.padding.medium
                implicitWidth: pillLabel.implicitWidth + Tokens.padding.large * 2
                implicitHeight: pillLabel.implicitHeight + Tokens.padding.small * 2
                radius: Tokens.rounding.full
                color: Colours.palette.m3primary

                StyledText {
                    id: pillLabel

                    anchors.centerIn: parent
                    text: Tr.tr("Button")
                    color: Colours.palette.m3onPrimary
                    font: Tokens.font.label.large
                }
            }

            StyledRect {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: Tokens.padding.medium
                implicitWidth: canvas.unit * 1.75
                implicitHeight: implicitWidth
                radius: Tokens.rounding.large
                color: Colours.palette.m3tertiaryContainer

                MaterialIcon {
                    anchors.centerIn: parent
                    text: "edit"
                    color: Colours.palette.m3onTertiaryContainer
                    fontStyle: Tokens.font.icon.medium
                }
            }
        }
    }

    // Fluent 2: a mica window with contained corners, a navigation rail with its accent bar and an
    // acrylic card with an accent button. Mica is the surface tinted by the accent; acrylic is a
    // translucent high surface over it; Fluent's 4/8 px radii are the extraSmall/small shape tokens.
    Component {
        id: fluentPreview

        StyledRect {
            id: mica

            property bool active
            readonly property real unit: height / 6

            color: Qt.tint(Colours.palette.m3surfaceContainerLowest, Qt.alpha(Colours.palette.m3primary, 0.08))
            radius: Tokens.rounding.small
            border.width: 1
            border.color: Colours.palette.m3outlineVariant

            Row {
                id: captions

                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: Tokens.padding.small
                anchors.topMargin: Tokens.padding.extraSmall
                spacing: Tokens.spacing.medium

                Repeater {
                    model: ["remove", "crop_square", "close"]

                    MaterialIcon {
                        required property string modelData

                        text: modelData
                        color: Colours.palette.m3onSurfaceVariant
                        fontStyle: Tokens.font.icon.small
                    }
                }
            }

            Column {
                id: rail

                anchors.left: parent.left
                anchors.top: captions.bottom
                anchors.leftMargin: Tokens.padding.small
                anchors.topMargin: Tokens.padding.extraSmall
                width: mica.width * 0.28
                spacing: Tokens.spacing.extraSmall

                Repeater {
                    model: 3

                    StyledRect {
                        id: navItem

                        required property int index

                        width: rail.width
                        height: mica.unit * 0.8
                        radius: Tokens.rounding.extraSmall
                        color: index === 0 ? Qt.alpha(Colours.palette.m3onSurface, 0.08) : "transparent"

                        StyledRect {
                            visible: navItem.index === 0
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            width: Tokens.padding.extraSmall
                            height: parent.height * 0.5
                            radius: Tokens.rounding.full
                            color: Colours.palette.m3primary
                        }

                        StyledRect {
                            anchors.left: parent.left
                            anchors.leftMargin: Tokens.padding.small + Tokens.padding.extraSmall
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width * (navItem.index === 0 ? 0.55 : 0.45)
                            height: Tokens.padding.small * 0.75
                            radius: Tokens.rounding.extraSmall
                            color: navItem.index === 0 ? Colours.palette.m3onSurface : Colours.palette.m3outline
                        }
                    }
                }
            }

            StyledRect {
                id: acrylic

                anchors.left: rail.right
                anchors.right: parent.right
                anchors.top: captions.bottom
                anchors.bottom: parent.bottom
                anchors.margins: Tokens.padding.small
                anchors.topMargin: Tokens.padding.extraSmall
                radius: Tokens.rounding.small
                color: Qt.alpha(Colours.palette.m3surfaceContainerHighest, 0.72)
                border.width: 1
                border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)

                Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Tokens.padding.small
                    spacing: Tokens.spacing.small

                    StyledRect {
                        width: parent.width * 0.6
                        height: Tokens.padding.small * 0.75
                        radius: Tokens.rounding.extraSmall
                        color: Colours.palette.m3onSurface
                    }

                    StyledRect {
                        width: parent.width * 0.85
                        height: Tokens.padding.extraSmall
                        radius: Tokens.rounding.extraSmall
                        color: Colours.palette.m3outlineVariant
                    }
                }

                Row {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: Tokens.padding.small
                    spacing: Tokens.spacing.small

                    StyledRect {
                        implicitWidth: accentLabel.implicitWidth + Tokens.padding.medium * 2
                        implicitHeight: accentLabel.implicitHeight + Tokens.padding.extraSmall * 2
                        radius: Tokens.rounding.extraSmall
                        color: Colours.palette.m3primary

                        StyledText {
                            id: accentLabel

                            anchors.centerIn: parent
                            text: Tr.tr("Button")
                            color: Colours.palette.m3onPrimary
                            font: Tokens.font.label.medium
                        }
                    }

                    StyledRect {
                        implicitWidth: neutralLabel.implicitWidth + Tokens.padding.medium * 2
                        implicitHeight: neutralLabel.implicitHeight + Tokens.padding.extraSmall * 2
                        radius: Tokens.rounding.extraSmall
                        color: Colours.palette.m3surfaceContainerLowest
                        border.width: 1
                        border.color: Colours.palette.m3outlineVariant

                        StyledText {
                            id: neutralLabel

                            anchors.centerIn: parent
                            text: Tr.tr("Cancel")
                            color: Colours.palette.m3onSurface
                            font: Tokens.font.label.medium
                        }
                    }
                }
            }
        }
    }

    // One design system: preview on top, then its name with a check (selected) or a WIP chip, and a line
    // of description. A WIP system is disabled: no state layer, M3 disabled opacity, the chip breathes on hover.
    component DesignCard: StyledRect {
        id: card

        required property string system
        required property string name
        required property string description
        required property bool wip
        required property Component preview
        readonly property bool selected: !wip && root.current === system
        readonly property bool hovered: wip ? wipHover.hovered : stateLayer.containsMouse

        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredWidth: 1
        Layout.alignment: Qt.AlignTop
        implicitHeight: content.implicitHeight + Tokens.padding.large * 2

        radius: Tokens.rounding.extraLarge
        color: selected ? Colours.layer(Colours.palette.m3secondaryContainer, 2) : Colours.tPalette.m3surfaceContainer
        border.width: 2
        border.color: selected ? Colours.palette.m3primary : "transparent"

        Accessible.role: Accessible.RadioButton
        Accessible.name: name
        Accessible.description: description
        Accessible.checked: selected

        StateLayer {
            id: stateLayer

            visible: !card.wip
            disabled: card.wip
            color: card.selected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
            // Material is the only system and is always selected: a click only ripples.
        }

        HoverHandler {
            id: wipHover

            enabled: card.wip
            cursorShape: Qt.ForbiddenCursor
        }

        ColumnLayout {
            id: content

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Tokens.padding.large
            spacing: Tokens.spacing.medium

            Loader {
                id: previewLoader

                Layout.fillWidth: true
                Layout.preferredHeight: Tokens.spacing.extraExtraLarge * 3
                sourceComponent: card.preview
                // Dimmed but still legible: the preview is what shows where Fluent 2 is going.
                opacity: card.wip ? 0.6 : 1
                scale: card.selected && card.hovered ? 1.02 : 1

                Binding {
                    target: previewLoader.item
                    property: "active"
                    value: card.hovered && !card.wip
                    when: previewLoader.status === Loader.Ready
                }

                Behavior on scale {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.small

                StyledText {
                    Layout.fillWidth: true
                    text: card.name
                    font: Tokens.font.title.medium
                    color: card.wip ? Qt.alpha(Colours.palette.m3onSurface, 0.38) : card.selected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                    elide: Text.ElideRight
                }

                MaterialIcon {
                    visible: card.selected
                    text: "check_circle"
                    fill: 1
                    color: Colours.palette.m3primary
                    fontStyle: Tokens.font.icon.medium
                }

                Chip {
                    visible: card.wip
                    icon: "construction"
                    // TRANSLATORS: "work in progress", shown on a design system that is not available yet
                    text: Tr.tr("WIP")
                    accent: Colours.palette.m3tertiary
                    onAccent: Colours.palette.m3onTertiary
                    pulsing: card.hovered
                }
            }

            StyledText {
                Layout.fillWidth: true
                text: card.wip && card.hovered ? Tr.tr("In development: not selectable yet") : card.description
                animate: true
                font: Tokens.font.body.small
                color: card.selected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                wrapMode: Text.WordWrap
            }
        }
    }
}
