pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Wysun.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.launcher.services
import qs.modules.nexus.common

// Theme picker: fixed schemes, Material You (wallpaper or seed) with variant and mode.
PageBase {
    id: root

    readonly property var fixedThemes: [
        {id: "space-black", scheme: "space-black", label: "Space Black", note: "Oscuro de base negra"},
        {id: "tokyo", scheme: "tokyo", label: "Tokyo", note: "Oscuro azulado"},
        {id: "severance", scheme: "severance", label: "Severance", note: "Oscuro verdoso"},
        {id: "fluent:light", scheme: "light", label: "Fluent claro", note: "Estilo Windows 11, claro"},
        {id: "fluent:dark", scheme: "dark", label: "Fluent oscuro", note: "Estilo Windows 11, oscuro"}
    ]
    readonly property bool dynamicActive: Colours.scheme === "dynamic"
    property string status: ""
    property bool failed: false
    property string seedText: ""

    function variantOptions(): var {
        const out = [{value: "auto", label: "Automática (según el fondo)"}];
        for (let i = 0; i < M3Variants.list.length; i++)
            out.push({value: M3Variants.list[i].variant, label: M3Variants.list[i].name});
        return out;
    }

    function variantNote(): string {
        for (let i = 0; i < M3Variants.list.length; i++)
            if (M3Variants.list[i].variant === Schemes.currentVariant)
                return M3Variants.list[i].description;
        return "";
    }

    function swatches(id: string): var {
        const entry = Schemes.list.find(s => s.name === id);
        const c = entry?.colours;
        return c ? [c.primary, c.secondary, c.tertiary, c.surface] : [];
    }

    function apply(args: var): void {
        if (run.running)
            return;
        status = "Aplicando…";
        failed = false;
        run.command = ["wysun", "scheme", "set"].concat(args);
        run.running = true;
    }

    title: "Tema y colores"
    isSubPage: true
    Component.onCompleted: Schemes.reload()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        // Live preview of the palette in use.
        StyledRect {
            Layout.fillWidth: true
            implicitHeight: Tokens.sizes.nexus.minHeight / 6
            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainer

            RowLayout {
                anchors.fill: parent
                anchors.margins: Tokens.padding.large
                spacing: Tokens.spacing.small

                Repeater {
                    model: [Colours.palette.m3primary, Colours.palette.m3secondary, Colours.palette.m3tertiary, Colours.palette.m3primaryContainer, Colours.palette.m3secondaryContainer, Colours.palette.m3surfaceContainerHigh, Colours.palette.m3error]

                    StyledRect {
                        required property color modelData

                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: Tokens.rounding.medium
                        color: modelData
                    }
                }
            }
        }

        StyledText {
            Layout.fillWidth: true
            Layout.leftMargin: Tokens.padding.small
            Layout.topMargin: Tokens.spacing.small
            text: (root.dynamicActive ? "Material You · " + (Colours.light ? "claro" : "oscuro") + " · " + (Schemes.currentVariant || "") : "Tema fijo · " + (root.fixedThemes.find(t => t.scheme === Colours.scheme)?.label ?? Colours.scheme))
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.label.medium
        }

        SectionHeader {
            text: "Temas fijos"
        }

        Repeater {
            model: root.fixedThemes

            RowButton {
                id: row

                required property var modelData
                required property int index

                first: index === 0
                last: index === root.fixedThemes.length - 1
                icon: "palette"
                text: modelData.label
                subtext: modelData.note
                trailingIcon: !root.dynamicActive && Colours.scheme === modelData.scheme ? "check_circle" : ""
                color: !root.dynamicActive && Colours.scheme === modelData.scheme ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
                onClicked: root.apply([modelData.id])

                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: Tokens.padding.extraLarge * 2
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Tokens.spacing.extraSmall

                    Repeater {
                        model: root.swatches(row.modelData.id)

                        Rectangle {
                            required property string modelData

                            implicitWidth: Tokens.padding.large * 1.5
                            implicitHeight: implicitWidth
                            radius: implicitWidth / 2
                            color: "#" + modelData
                            border.width: 1
                            border.color: Colours.palette.m3outlineVariant
                        }
                    }
                }
            }
        }

        SectionHeader {
            text: "Material You"
        }

        RowButton {
            first: true
            icon: "wallpaper"
            text: "Colores del fondo"
            subtext: "El acento se toma del wallpaper actual"
            trailingIcon: root.dynamicActive ? "check_circle" : ""
            color: root.dynamicActive ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
            onClicked: root.apply(["--dynamic", "--seed", "none"])
        }

        OptionRow {
            label: "Modo"
            subtext: "Claro u oscuro; automático lo deduce del fondo"
            options: [{value: "auto", label: "Automático"}, {value: "light", label: "Claro"}, {value: "dark", label: "Oscuro"}]
            current: Colours.light ? "light" : "dark"
            onPicked: value => root.apply(["--dynamic", "--mode", value])
        }

        OptionRow {
            label: "Variante"
            subtext: root.variantNote()
            options: root.variantOptions()
            current: Schemes.currentVariant
            onPicked: value => root.apply(["--dynamic", "--variant", value])
        }

        TextFieldRow {
            label: "Acento manual"
            subtext: "#RRGGBB en lugar del fondo"
            value: root.seedText
            maximumLength: 7
            smallField: true
            onValueEdited: value => root.seedText = value
        }

        RowLayout {
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.small

            ActionButton {
                text: "Aplicar acento"
                disabled: !/^#[0-9a-fA-F]{6}$/.test(root.seedText)
                onClicked: root.apply(["--dynamic", "--seed", root.seedText])
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Quitar acento"
                onClicked: {
                    root.seedText = "";
                    root.apply(["--dynamic", "--seed", "none"]);
                }
            }

            ActionButton {
                type: TextButton.Tonal
                text: "Elegir fondo"
                onClicked: root.nState.openSubPage(1)
            }
        }

        StatusLine {
            text: root.status
            error: root.failed
        }

        Process {
            id: run

            stderr: StdioCollector {
                id: errors
            }
            onExited: code => {
                root.failed = code !== 0;
                root.status = code === 0 ? "Tema aplicado." : (errors.text.trim() || "No se pudo aplicar el tema.");
                Schemes.reload();
            }
        }
    }
}
