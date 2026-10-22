// Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
// Base: 6c70d5cb0cbf31413d300699540c858ad28c1539; véanse LICENSE y UPSTREAM.json.
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Wysun
import Wysun.Config
import Wysun.I18n
import Wysun.Multimedia
import Wysun.Shaders
import Wysun.State
import qs.components
import qs.components.filedialog
import qs.services
import qs.utils

Item {
    id: root

    readonly property transitionShader shader: {
        CUtils.dependency(Config.background.wallpaperTransition);
        let transition = CUtils.enumToString(Config.background, "wallpaperTransition");
        if (!transition)
            return Shaders.crossfade;

        transition = transition[0].toLowerCase() + transition.slice(1);
        return Shaders[transition] ?? Shaders.crossfade;
    }

    readonly property string screenName: (QsWindow.window as QsWindow)?.screen?.name || ""
    property string source: Wallpapers.forOutput(screenName)
    property ShaderEffectSource currentCapture: capture1
    property real transitionProgress: 1
    property bool completed

    onSourceChanged: {
        transitionAnim.stop();

        if (transitionProgress < 1) {
            currentCapture = currentCapture === capture1 ? capture2 : capture1;
            currentCapture.sourceItem = transition;
        } else {
            currentCapture.sourceItem = live;
        }

        currentCapture.visible = true;
        currentCapture.scheduleUpdate();
    }

    Component.onCompleted: {
        completed = true;
        live.source = source;
    }

    Loader {
        asynchronous: true
        anchors.fill: parent

        active: root.completed && !root.source

        sourceComponent: StyledRect {
            color: Colours.palette.m3surfaceContainer

            Row {
                anchors.centerIn: parent
                spacing: Tokens.spacing.largeIncreased

                MaterialIcon {
                    text: "sentiment_stressed"
                    color: Colours.palette.m3onSurfaceVariant
                    fontStyle: Tokens.font.icon.builders.extraLarge.scale(5).build()
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Tokens.spacing.small

                    StyledText {
                        text: Tr.tr("Wallpaper missing?")
                        color: Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.body.builders.large.size(28 * 2).weight(Font.Bold).build()
                    }

                    StyledRect {
                        implicitWidth: selectWallText.implicitWidth + Tokens.padding.extraLargeIncreased
                        implicitHeight: selectWallText.implicitHeight + Tokens.padding.small

                        radius: Tokens.rounding.full
                        color: Colours.palette.m3primary

                        FileDialog {
                            id: dialog

                            title: Tr.tr("Select a wallpaper")
                            filterLabel: Tr.tr("Image files")
                            filters: Images.validImageExtensions
                            onAccepted: path => Wallpapers.setWallpaper(path)
                        }

                        StateLayer {
                            radius: parent.radius
                            color: Colours.palette.m3onPrimary
                            onClicked: dialog.open()
                        }

                        StyledText {
                            id: selectWallText

                            anchors.centerIn: parent

                            text: Tr.tr("Set it now!")
                            color: Colours.palette.m3onPrimary
                            font: Tokens.font.body.large
                        }
                    }
                }
            }
        }
    }

    NumberAnimation on transitionProgress {
        id: transitionAnim

        running: false
        duration: root.shader.duration * Tokens.anim.durations.scale
        easing: root.shader.easing
        to: 1
    }

    ShaderEffectSource {
        id: capture1

        anchors.fill: parent
        live: false
        visible: false

        onScheduledUpdateCompleted: {
            visible = false;
            transition.from = this;
            root.transitionProgress = 0;
            live.source = root.source;
        }
    }

    ShaderEffectSource {
        id: capture2

        anchors.fill: parent
        live: false
        visible: false

        onScheduledUpdateCompleted: {
            visible = false;
            transition.from = this;
            root.transitionProgress = 0;
            live.source = root.source;
        }
    }

    WallpaperVisual {
        id: live

        anchors.fill: parent
        playing: PersistentState.wallpaperPlaying && !Wallpapers.suspendedOn(root.screenName)
        animate: false
        layer.enabled: true

        onReadyChanged: {
            if (ready && source === root.source)
                transitionAnim.start();
        }
    }

    ShaderEffect {
        id: transition

        property Item from
        property Item to: live
        property real progress: root.transitionProgress

        anchors.fill: parent
        visible: root.transitionProgress < 1
        fragmentShader: root.shader.url
    }
}
