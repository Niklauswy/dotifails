pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.components.effects
import qs.services
import qs.modules.launcher.services

// The launcher turning into the editor window (see Editor.qml for the sequence). The morph starts as an exact copy
// of the launcher (a snapshot of its surface), which dissolves while the surface takes the terminal's colour and
// corners and the previewed code moves to where Neovim draws it, in the terminal's font. Once the terminal's window
// exists, the panel flies onto its real tile and dissolves into it. It never takes input.
Scope {
    // `wysun-shell ipc call editor open <path>`: the same hand-over without the launcher, from where its panel would sit.
    IpcHandler {
        target: "editor"

        function open(path: string): bool {
            const screen = Quickshell.screens.find(s => s.name === Hypr.focusedMonitor?.name) ?? Quickshell.screens[0];
            if (!screen || !path)
                return false;
            const w = Math.min(520, screen.width - 96), h = Math.min(420, screen.height - 96);
            Editor.open(screen, Qt.rect((screen.width - w) / 2, screen.height * 0.2, w, h), Colours.palette.m3surface, path, null, null);
            return true;
        }
    }

    Variants {
        model: Quickshell.screens

        delegate: StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property bool shown: Editor.active && Editor.screenName === modelData.name
            // a: the launcher becoming the editor, in place. b: the flight onto the window's tile.
            property real a: Editor.morphed ? 1 : 0
            property real b: Editor.flying ? 1 : 0
            // Leaves as the window underneath becomes visible.
            property real fade: Editor.ready ? 0 : 1

            Behavior on a {
                enabled: Editor.active

                NumberAnimation {
                    duration: 480
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] // standard
                }
            }
            Behavior on b {
                enabled: Editor.active

                NumberAnimation {
                    duration: Editor.flight
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [0.05, 0.7, 0.1, 1, 1, 1] // emphasized decelerate: quick start, soft landing
                }
            }
            Behavior on fade {
                enabled: Editor.active

                NumberAnimation {
                    duration: 200
                    easing.type: Easing.OutQuad
                }
            }

            function lerp(p: real, q: real, t: real): real {
                return p + (q - p) * t;
            }

            function mix(p: color, q: color, t: real): color {
                return Qt.rgba(lerp(p.r, q.r, t), lerp(p.g, q.g, t), lerp(p.b, q.b, t), lerp(p.a, q.a, t));
            }

            Tokens.screen: modelData.name
            name: "launcher-morph"
            screen: modelData
            visible: shown
            anchors.top: true
            anchors.bottom: true
            anchors.left: true
            anchors.right: true
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            mask: Region {}

            // The launcher's own shadow, fading as it stops being the launcher.
            Elevation {
                x: card.x
                y: card.y
                width: card.width
                height: card.height
                radius: card.radius
                level: 4
                opacity: card.opacity * (1 - win.a)
            }

            Rectangle {
                id: card

                x: win.lerp(Editor.panelRect.x, Editor.tile.x, win.b)
                y: win.lerp(Editor.panelRect.y, Editor.tile.y, win.b)
                width: win.lerp(Editor.panelRect.width, Editor.tile.width, win.b)
                height: win.lerp(Editor.panelRect.height, Editor.tile.height, win.b)
                radius: win.lerp(Editor.panelRadius, Tokens.rounding.small, win.a)
                // From the launcher's surface to the terminal's own background (it draws no blur, neither does this).
                color: win.mix(Qt.alpha(Editor.panelColour, 1), Qt.alpha(Editor.termBg, Math.min(1, Editor.termAlpha + 0.1)), win.a)
                opacity: win.fade
                clip: true

                // The launcher as it was when Enter was pressed; it dissolves in the first half of the morph.
                Image {
                    width: Editor.panelRect.width
                    height: Editor.panelRect.height
                    source: Editor.snapshot
                    visible: Editor.snapshot !== ""
                    opacity: 1 - Math.min(1, win.a / 0.55)
                    smooth: true
                    cache: false
                }

                // The previewed code, laid out once in the terminal's font and size and rendered to a texture: it
                // starts at the preview's place and scale inside the launcher and ends where Neovim draws its first
                // line (below its tab line). Only the texture moves and scales; nothing is re-laid out per frame.
                Item {
                    id: body

                    readonly property real startPx: Tokens.font.mono.small.pixelSize > 0 ? Tokens.font.mono.small.pixelSize : Tokens.font.mono.small.pointSize * 96 / 72
                    readonly property real inset: Tokens.padding.medium * Editor.textScale

                    x: win.lerp(Editor.from.x - Editor.panelRect.x + inset, Editor.termPad, win.a)
                    y: win.lerp(Editor.from.y - Editor.panelRect.y + inset, Editor.termPad + Editor.termPx * 1.25, win.a)
                    width: 2400
                    height: 1600
                    transformOrigin: Item.TopLeft
                    scale: win.lerp(startPx * Editor.textScale / Editor.termPx, 1, win.a)
                    // Over the snapshot's own copy of the code it fades in, so the two never show as a double image.
                    opacity: Editor.snapshot !== "" ? Math.min(1, win.a / 0.35) : 1
                    visible: Editor.codeHtml !== ""
                    layer.enabled: visible

                    Row {
                        spacing: Editor.termPx * 0.6

                        StyledText {
                            text: Array.from({length: Editor.codeText.split("\n").length}, (_, i) => i + 1).join("\n")
                            font.family: Editor.termFont
                            font.pixelSize: Editor.termPx
                            color: Editor.codeLineNr
                            horizontalAlignment: Text.AlignRight
                        }
                        StyledText {
                            text: Editor.codeHtml
                            textFormat: Text.StyledText
                            font.family: Editor.termFont
                            font.pixelSize: Editor.termPx
                            color: Editor.codeFg
                        }
                    }
                }

                // Without a styled preview (IPC, no Neovim theme): a terminal glyph and the file name.
                Column {
                    anchors.centerIn: parent
                    spacing: Tokens.spacing.medium
                    visible: Editor.codeHtml === ""
                    opacity: win.a

                    MaterialIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "terminal"
                        color: Colours.palette.m3primary
                        fontStyle: Tokens.font.icon.builders.extraLarge.build()
                    }
                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: Editor.title
                        font: Tokens.font.mono.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }
            }
        }
    }
}
