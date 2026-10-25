pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Wysun.Components
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.controls
import qs.components.images
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    title: Tr.tr("Wallpaper & style")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        ClipRect {
            id: wallWrapper

            Layout.alignment: Qt.AlignHCenter
            implicitWidth: {
                const screen = root.nState.screen;
                return implicitHeight / screen.height * screen.width;
            }
            implicitHeight: {
                const screen = root.nState.screen;
                const cWidth = root.cappedWidth;
                return Math.min(Math.round(cWidth * 0.4), cWidth / screen.width * screen.height);
            }

            color: Colours.tPalette.m3surfaceContainer
            radius: Tokens.rounding.large

            Item {
                anchors.fill: parent

                Loader {
                    id: wallIndicatorLoader

                    anchors.centerIn: parent

                    opacity: 0
                    active: opacity > 0

                    sourceComponent: StyledRect {
                        implicitWidth: wallLoadingIndicator.implicitSize + Tokens.padding.largeIncreased * 2
                        implicitHeight: wallLoadingIndicator.implicitSize + Tokens.padding.largeIncreased * 2

                        color: Colours.palette.m3primaryContainer
                        radius: Tokens.rounding.full

                        LoadingIndicator {
                            id: wallLoadingIndicator

                            anchors.centerIn: parent
                            containsIcon: true
                            implicitSize: Math.min(wallWrapper.implicitWidth, wallWrapper.implicitHeight) * 0.4
                        }
                    }

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }
                }

                Timer {
                    id: wallLoadDebounceTimer

                    interval: 100
                    onTriggered: {
                        if (wallImg.status !== Image.Ready)
                            wallIndicatorLoader.opacity = 1;
                    }
                }

                FadeImage {
                    id: wallImg

                    anchors.fill: parent
                    source: Wallpapers.forOutput(root.nState.screen.name)
                    preventInit: wallIndicatorLoader.opacity > 0
                    fadeOutAnim: Anim.DefaultEffects
                    fadeInAnim: Anim.SlowEffects

                    onSourceChanged: wallLoadDebounceTimer.restart()

                    onStatusChanged: {
                        if (status === Image.Ready) {
                            wallLoadDebounceTimer.stop();
                            wallIndicatorLoader.opacity = 0;
                        }
                    }
                }

                Row {
                    id: swatches

                    readonly property real size: Math.round(wallWrapper.implicitHeight * 0.14)

                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: Tokens.padding.large
                    spacing: -Math.round(size * 0.3)

                    Swatch {
                        size: swatches.size
                        color: Colours.palette.m3primary
                    }

                    Swatch {
                        size: swatches.size
                        color: Colours.palette.m3secondary
                    }

                    Swatch {
                        size: swatches.size
                        color: Colours.palette.m3tertiary
                    }

                    Swatch {
                        size: swatches.size
                        color: Colours.palette.m3primaryContainer
                    }
                }
            }
        }

        StyledText {
            Layout.alignment: Qt.AlignHCenter
            text: Tr.tr("Colours follow your wallpaper")
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.body.medium
        }

        IconTextButton {
            Layout.alignment: Qt.AlignHCenter
            icon: "view_carousel"
            text: Tr.tr("Browse as carousel")
            font: Tokens.font.body.large
            isRound: true
            shapeMorph: true
            horizontalPadding: Tokens.padding.extraLarge
            verticalPadding: Tokens.padding.medium
            onClicked: Quickshell.execDetached(["wysun", "shell", "wallpapers"])
        }

        ButtonRow {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Tokens.spacing.small
            spacing: Tokens.spacing.extraSmall

            ModeButton {
                icon: "brightness_auto"
                text: Tr.tr("Auto")
                mode: "auto"
            }

            ModeButton {
                icon: "light_mode"
                text: Tr.tr("Light")
                mode: "light"
            }

            ModeButton {
                icon: "dark_mode"
                text: Tr.tr("Dark")
                mode: "dark"
            }
        }

        ToggleRow {
            Layout.topMargin: Tokens.spacing.small

            first: true
            last: true
            text: Tr.tr("Transparency")
            // TRANSLATORS: %1/%2 = opacity values from 0 to 1 for the base surface and layered surfaces
            subtext: Tr.tr("Base %1, layers %2").arg(Colours.transparency.base).arg(Colours.transparency.layers)
            checked: Colours.transparency.enabled
            onToggled: GlobalConfig.appearance.transparency.enabled = checked
        }
    }

    // One option of the colour mode: Auto follows the wallpaper, Light and Dark override it.
    component ModeButton: IconTextButton {
        required property string mode

        font: Tokens.font.body.large
        type: IconTextButton.Tonal
        isRound: true
        shapeMorph: true
        horizontalPadding: Tokens.padding.extraLarge
        verticalPadding: Tokens.padding.medium
        checked: Colours.modePreference === mode
        onClicked: Colours.setMode(mode)
    }

    // A swatch of the Material role that currently follows the wallpaper.
    component Swatch: StyledRect {
        required property real size

        implicitWidth: size
        implicitHeight: size
        radius: Tokens.rounding.full
        border.width: 2
        border.color: Colours.palette.m3surfaceContainer
    }
}
