pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.components.effects
import qs.components.misc
import qs.services

// A pill with the recording time, pause and stop, on the output being recorded.
// It never sits inside the recorded area (the screen shows what the video shows):
// above or below the region, or hidden when there is no room outside it.
Scope {
    id: root

    readonly property bool shown: Recorder.active

    Ref {
        service: Recorder
    }

    // wysun-shell record start | toggle | pause | stop
    IpcHandler {
        function start(): void {
            Recorder.start();
        }

        function toggle(): void {
            Recorder.toggle();
        }

        function pause(): void {
            if (Recorder.running)
                Recorder.togglePause();
        }

        function stop(): void {
            if (Recorder.active)
                Recorder.stop();
        }

        // Draw on the screen while recording; again, or Esc, puts the tools away.
        function annotate(): void {
            if (Recorder.running)
                Recorder.annotating = !Recorder.annotating;
        }

        target: "recorder"
    }

    Variants {
        model: root.shown ? Screens.screens : []

        StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property bool owner: Recorder.screenName === modelData.name
            readonly property real gap: Tokens.sizes.screenshot.toolbarGap + 22
            readonly property rect region: Recorder.region
            // Free band above or below the region; none when the region covers the output.
            readonly property real bandY: region.y >= pill.height + gap * 2 ? region.y - pill.height - gap : region.y + region.height + pill.height + gap * 2 <= modelData.height ? region.y + region.height + gap : -1

            Tokens.screen: modelData.name
            screen: modelData
            name: "recording-hud"
            // On a recorded output only the free band is allowed; other outputs keep it on top.
            visible: owner ? bandY >= 0 && !Recorder.wholeOutput : true
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            anchors.top: true
            anchors.left: true
            margins.top: owner ? Math.max(0, bandY) : gap
            margins.left: owner ? Math.max(gap, Math.min(modelData.width - pill.width - gap, region.x + region.width / 2 - pill.width / 2)) : (modelData.width - pill.width) / 2
            implicitWidth: pill.implicitWidth
            implicitHeight: pill.implicitHeight
            color: "transparent"

            StyledRect {
                id: pill

                implicitWidth: row.implicitWidth + Tokens.padding.small * 2
                implicitHeight: row.implicitHeight + Tokens.padding.small * 2
                radius: Tokens.rounding.full
                color: Colours.palette.m3surfaceContainer
                border.width: 1
                border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)

                Elevation {
                    anchors.fill: parent
                    radius: pill.radius
                    level: 3
                    z: -1
                }

                RowLayout {
                    id: row

                    anchors.centerIn: parent
                    spacing: Tokens.spacing.small

                    StyledRect {
                        Layout.leftMargin: Tokens.padding.small
                        implicitWidth: Tokens.spacing.small * 1.5
                        implicitHeight: implicitWidth
                        radius: Tokens.rounding.full
                        color: Recorder.paused ? Colours.palette.m3tertiary : Colours.palette.m3error

                        SequentialAnimation on opacity {
                            running: Recorder.running && !Recorder.paused
                            alwaysRunToEnd: true
                            loops: Animation.Infinite

                            Anim {
                                from: 1
                                to: 0.25
                                duration: Tokens.anim.durations.large
                                easing: Tokens.anim.emphasizedAccel
                            }
                            Anim {
                                from: 0.25
                                to: 1
                                duration: Tokens.anim.durations.extraLarge
                                easing: Tokens.anim.emphasizedDecel
                            }
                        }
                    }

                    StyledText {
                        text: {
                            if (Recorder.countdown > 0)
                                return Tr.trCtx("Starting in %1", "recording status").arg(Recorder.countdown);
                            if (!Recorder.running)
                                return Tr.trCtx("Starting…", "recording status");
                            const e = Recorder.elapsed, h = Math.floor(e / 3600), m = Math.floor((e % 3600) / 60), s = Math.floor(e % 60).toString().padStart(2, "0");
                            return h > 0 ? `${h}:${m.toString().padStart(2, "0")}:${s}` : `${m}:${s}`;
                        }
                        font: Tokens.font.mono.medium
                        animate: true
                    }

                    IconButton {
                        visible: Recorder.countdown === 0
                        enabled: Recorder.running
                        shapeMorph: true
                        isRound: true
                        icon: Recorder.paused ? "play_arrow" : "pause"
                        type: IconButton.Tonal
                        font: Tokens.font.icon.medium
                        onClicked: Recorder.togglePause()
                    }

                    IconButton {
                        visible: Recorder.countdown === 0
                        enabled: Recorder.running
                        shapeMorph: true
                        isRound: true
                        icon: "draw"
                        isToggle: true
                        checked: Recorder.annotating
                        type: IconButton.Tonal
                        font: Tokens.font.icon.medium
                        onClicked: Recorder.annotating = !Recorder.annotating
                    }

                    IconButton {
                        enabled: Recorder.running || Recorder.countdown > 0
                        shapeMorph: true
                        isRound: true
                        icon: Recorder.countdown > 0 ? "close" : "stop"
                        inactiveColour: Colours.palette.m3error
                        inactiveOnColour: Colours.palette.m3onError
                        font: Tokens.font.icon.medium
                        onClicked: Recorder.stop()
                    }
                }
            }
        }
    }
}
