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
    readonly property Item visual: live
    property real transitionProgress: 1
    property bool completed
    readonly property var motion: TokenConfig.appearance.wallpaperMotion
    readonly property bool cinematicZoom: shader.url.toString() === Shaders.zoomBlurPull.url.toString()
    readonly property bool liquidRift: shader.url.toString() === Shaders.liquidRift.url.toString()
    readonly property ShellScreen screen: (QsWindow.window as QsWindow)?.screen ?? null
    // Desktop point where the rift opens (centre of the focused screen) and how far its
    // front must travel to clear every screen; fixed when each transition starts.
    property point riftOrigin
    property real riftReach: 1

    function aimRift(): void {
        const screens = Quickshell.screens;
        const focus = screens.find(s => s.name === Hypr.focusedMonitor?.name) ?? root.screen ?? screens[0];
        if (!focus)
            return;
        const ox = focus.x + focus.width / 2, oy = focus.y + focus.height / 2;
        let reach = 1;
        for (const s of screens)
            for (const [cx, cy] of [[s.x, s.y], [s.x + s.width, s.y], [s.x, s.y + s.height], [s.x + s.width, s.y + s.height]])
                reach = Math.max(reach, Math.hypot(cx - ox, cy - oy));
        riftOrigin = Qt.point(ox, oy);
        riftReach = reach;
    }

    onSourceChanged: {
        transitionAnim.stop();
        firstFrame.stop();
        aimRift();

        // Nothing on screen yet (shell start): show the wallpaper without a transition
        // from an empty capture.
        if (!completed || !live.source.toString()) {
            if (completed)
                live.source = source;
            return;
        }

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
        duration: (root.liquidRift ? root.motion.riftDuration : root.cinematicZoom ? root.motion.duration : root.shader.duration) * Tokens.anim.durations.scale
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

        onReadyChanged: {
            if (ready && source === root.source)
                firstFrame.restart();
        }
    }

    // "Ready" means decoded; give the layer a couple of frames to draw it so the
    // transition never reveals an empty (black) surface.
    Timer {
        id: firstFrame

        interval: 34
        onTriggered: {
            if (live.ready && live.source === root.source)
                transitionAnim.start();
        }
    }

    // The incoming wallpaper as the shader sees it. A source of its own, not
    // `live.layer`: a ShaderEffect keeps the texture provider it first resolved,
    // so a layer recreated for each transition left it sampling a stale frame
    // (the old wallpaper, or nothing). It only renders while a transition runs.
    ShaderEffectSource {
        id: incoming

        anchors.fill: parent
        sourceItem: root.transitionProgress < 1 ? root.visual : null
        live: true
        visible: false
    }

    ShaderEffect {
        id: transition

        property Item from
        property Item to: incoming
        property real progress: root.transitionProgress
        property real outgoingZoom: root.motion.outgoingZoom
        property real incomingZoom: root.motion.incomingZoom
        property real blurStrength: root.motion.blurStrength
        property real revealStart: root.motion.revealStart
        property real revealEnd: root.motion.revealEnd
        property real riftReach: root.riftReach
        property point riftOrigin: root.riftOrigin
        property point screenOrigin: Qt.point(root.screen?.x ?? 0, root.screen?.y ?? 0)
        property size screenSize: Qt.size(width, height)

        anchors.fill: parent
        visible: root.transitionProgress < 1
        fragmentShader: root.shader.url
    }
}
