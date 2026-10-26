// Theme: every m3 role as a swatch, the type scale, tonal elevation (Surface) and the interaction primitives.
import QtQuick
import WysunM3
import ".."

Page {
    id: page

    readonly property var roles: ["primary", "onPrimary", "primaryContainer", "onPrimaryContainer", "secondary", "onSecondary", "secondaryContainer", "onSecondaryContainer", "tertiary", "onTertiary", "tertiaryContainer", "onTertiaryContainer", "error", "onError", "errorContainer", "onErrorContainer", "surface", "onSurface", "surfaceVariant", "onSurfaceVariant", "surfaceContainerLowest", "surfaceContainerLow", "surfaceContainer", "surfaceContainerHigh", "surfaceContainerHighest", "outline", "outlineVariant", "inverseSurface", "inverseOnSurface", "inversePrimary"]

    Section {
        title: "Roles de color"
        note: "Theme.m3<rol>, directos del esquema del wallpaper (scheme.json) y en vivo."

        Repeater {
            model: page.roles

            Column {
                required property string modelData

                width: Metrics.textFieldMinWidth * 0.62
                spacing: Theme.spacing.extraSmall ?? 0

                Rectangle {
                    width: parent.width
                    height: Metrics.listItemOneLine
                    radius: Theme.rounding.medium ?? 0
                    color: Theme["m3" + parent.modelData]
                    border.width: Metrics.outlineWidth
                    border.color: Theme.m3outlineVariant
                }
                Label {
                    width: parent.width
                    role: "label.small"
                    text: parent.modelData
                    elide: Text.ElideRight
                }
            }
        }
    }

    Section {
        title: "Tipografía"

        Column {
            spacing: Theme.spacing.small ?? 0

            Repeater {
                model: ["headline.large", "headline.medium", "headline.small", "title.large", "title.medium", "title.small", "body.large", "body.medium", "body.small", "label.large", "label.medium", "label.small"]

                Label {
                    required property string modelData

                    role: modelData
                    text: modelData + " · Wysun Material 3 Expressive"
                }
            }
        }
    }

    Section {
        title: "Elevación tonal (Surface)"
        note: "Niveles 0-5 sobre surfaceContainerLow."

        Repeater {
            model: 6

            Surface {
                required property int index

                width: Metrics.fabLarge
                height: Metrics.fabLarge
                radius: Theme.rounding.large ?? 0
                container: Theme.m3surfaceContainerLow
                level: index

                Label {
                    anchors.centerIn: parent
                    role: "title.medium"
                    text: parent.index
                }
            }
        }
    }

    Section {
        title: "Estados e interacción"
        note: "StateLayer (8/12/12/16 %) y FocusRing (solo con teclado; pulsa Tab)."

        Rectangle {
            id: sample

            width: Metrics.textFieldMinWidth
            height: Metrics.listItemOneLine
            radius: Theme.rounding.large ?? 0
            color: Theme.m3surfaceContainerHighest
            focusPolicy: Qt.TabFocus
            activeFocusOnTab: true

            Label {
                anchors.centerIn: parent
                text: "Pasa el ratón o pulsa"
            }

            StateLayer {
                radius: sample.radius
                focused: sample.activeFocus
            }

            FocusRing {
                target: sample
            }
        }
    }
}
