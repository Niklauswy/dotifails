pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components.containers
import qs.services

// A short burst of confetti in the theme colours when a weekly limit resets (setting "confetti").
// The windows let every click through and close by themselves.
Scope {
    id: root

    property bool running
    readonly property int duration: Tokens.anim.durations.extraLarge * 6

    Connections {
        function onWeeklyReset(): void {
            root.running = true;
            stop.restart();
        }

        target: AiUsage
    }

    Timer {
        id: stop

        interval: root.duration
        onTriggered: root.running = false
    }

    LazyLoader {
        active: root.running

        Variants {
            model: Quickshell.screens

            StyledWindow {
                id: win

                required property ShellScreen modelData

                screen: modelData
                name: "ai-confetti"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                mask: Region {}
                color: "transparent"

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                Canvas {
                    id: canvas

                    readonly property var colours: [Colours.palette.m3primary, Colours.palette.m3tertiary, Colours.palette.m3secondary, Colours.palette.m3success, Colours.palette.m3primaryFixedDim, Colours.palette.m3tertiaryFixedDim]
                    property var pieces: []

                    anchors.fill: parent

                    Component.onCompleted: {
                        const out = [];
                        const size = Tokens.spacing.small;
                        for (let i = 0; i < 180; i++)
                            out.push({
                                x: width * (0.2 + Math.random() * 0.6),
                                y: height + size,
                                vx: (Math.random() - 0.5) * size * 1.2,
                                vy: -(size * 1.4 + Math.random() * size * 1.2),
                                r: Math.random() * 6.28,
                                s: size * (0.6 + Math.random() * 0.8),
                                c: colours[i % colours.length]
                            });
                        pieces = out;
                    }

                    onPaint: {
                        const ctx = getContext("2d");
                        ctx.reset();
                        for (const p of pieces) {
                            p.vy += Tokens.spacing.small / 28;
                            p.vx *= 0.99;
                            p.x += p.vx;
                            p.y += p.vy;
                            p.r += 0.15;
                            ctx.save();
                            ctx.translate(p.x, p.y);
                            ctx.rotate(p.r);
                            ctx.fillStyle = p.c;
                            ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2);
                            ctx.restore();
                        }
                    }

                    Timer {
                        interval: 16
                        running: true
                        repeat: true
                        onTriggered: canvas.requestPaint()
                    }
                }
            }
        }
    }
}
