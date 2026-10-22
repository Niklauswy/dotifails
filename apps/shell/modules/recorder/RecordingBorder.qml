pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services

// A frame around the area being recorded. It lives outside the area (the screen
// shows what the video shows), never takes input, and moves: dashes marching
// while it records, a soft pulse going outward, corners that settle in when it
// starts. Paused it stops and turns tertiary; during the countdown it is primary.
Scope {
    id: root

    Variants {
        model: Recorder.active ? Screens.screens : []

        StyledWindow {
            id: win

            required property ShellScreen modelData
            readonly property rect area: Recorder.region
            readonly property bool counting: Recorder.countdown > 0
            readonly property color tone: counting ? Colours.palette.m3primary : Recorder.paused ? Colours.palette.m3tertiary : Colours.palette.m3error
            readonly property real gap: 7
            readonly property real line: 3
            readonly property real reach: gap + line / 2
            // Edge of the frame around the area.
            readonly property rect frame: Qt.rect(area.x - reach, area.y - reach, area.width + reach * 2, area.height + reach * 2)

            Tokens.screen: modelData.name
            screen: modelData
            name: "recording-border"
            visible: Recorder.screenName === modelData.name && !Recorder.wholeOutput && area.width > 0
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            anchors.top: true
            anchors.bottom: true
            anchors.left: true
            anchors.right: true
            // Empty input region: clicks go to what is under the frame.
            mask: Region {}
            color: "transparent"

            Item {
                id: stage

                // Settles in from a little further out when it appears.
                property real arrive: 0

                x: win.frame.x
                y: win.frame.y
                width: win.frame.width
                height: win.frame.height
                opacity: arrive
                scale: 1 + (1 - arrive) * 0.04
                transformOrigin: Item.Center

                Component.onCompleted: arriveAnim.start()

                Anim {
                    id: arriveAnim

                    target: stage
                    property: "arrive"
                    from: 0
                    to: 1
                    type: Anim.SlowSpatial
                }

                // Pulse: a copy of the frame that drifts outward and fades.
                Rectangle {
                    id: pulse

                    property real t: 0

                    anchors.centerIn: parent
                    width: parent.width + t * 26
                    height: parent.height + t * 26
                    radius: Tokens.rounding.small + t * 13
                    color: "transparent"
                    border.width: win.line
                    border.color: win.tone
                    opacity: (1 - t) * 0.5
                    visible: Recorder.running && !Recorder.paused || win.counting

                    NumberAnimation on t {
                        from: 0
                        to: 1
                        duration: 1900
                        loops: Animation.Infinite
                        easing.type: Easing.OutCubic
                        running: pulse.visible
                    }
                }

                Shape {
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer

                    // Dashes that run around the area.
                    ShapePath {
                        strokeColor: Qt.alpha(win.tone, 0.85)
                        strokeWidth: win.line
                        fillColor: "transparent"
                        strokeStyle: ShapePath.DashLine
                        dashPattern: [5, 4]

                        NumberAnimation on dashOffset {
                            from: 0
                            to: -36
                            duration: win.counting ? 700 : 2400
                            loops: Animation.Infinite
                            running: win.counting || Recorder.running && !Recorder.paused
                        }

                        PathRectangle {
                            x: win.line / 2
                            y: win.line / 2
                            width: stage.width - win.line
                            height: stage.height - win.line
                            radius: Tokens.rounding.small
                        }
                    }

                    // Viewfinder corners.
                    Corner {
                        cx: win.line * 1.5
                        cy: win.line * 1.5
                        dx: 1
                        dy: 1
                    }

                    Corner {
                        cx: stage.width - win.line * 1.5
                        cy: win.line * 1.5
                        dx: -1
                        dy: 1
                    }

                    Corner {
                        cx: win.line * 1.5
                        cy: stage.height - win.line * 1.5
                        dx: 1
                        dy: -1
                    }

                    Corner {
                        cx: stage.width - win.line * 1.5
                        cy: stage.height - win.line * 1.5
                        dx: -1
                        dy: -1
                    }
                }
            }

            component Corner: ShapePath {
                property real cx
                property real cy
                property int dx
                property int dy
                readonly property real arm: 26

                strokeColor: win.tone
                strokeWidth: win.line * 2
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                startX: cx + dx * arm
                startY: cy

                PathLine {
                    x: cx
                    y: cy
                }

                PathLine {
                    x: cx
                    y: cy + dy * arm
                }
            }
        }
    }
}
