pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import M3Shapes
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services

// One label per screen while DisplayIdentify.showing: the position in Settings' display order, the
// connector name, the picture it is showing and a star on the primary. The windows let clicks through.
Scope {
    id: root

    // Left to right, top to bottom: the order Settings > Displays lists them in.
    readonly property var ordered: [...Quickshell.screens].sort((a, b) => a.y - b.y || a.x - b.x)

    LazyLoader {
        active: DisplayIdentify.alive

        Variants {
            model: root.ordered

            StyledWindow {
                id: win

                required property ShellScreen modelData
                readonly property int index: root.ordered.indexOf(modelData)
                readonly property bool shown: DisplayIdentify.showing
                readonly property var monitor: Hypr.monitorFor(modelData)
                readonly property string detail: `${modelData.width} × ${modelData.height}` + (monitor?.lastIpcObject?.refreshRate ? ` · ${Math.round(monitor.lastIpcObject.refreshRate)} Hz` : "")

                screen: modelData
                name: "identify"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                mask: Region {}

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                // Dims the screen a little so the label reads on any wallpaper.
                Rectangle {
                    anchors.fill: parent
                    color: Colours.palette.m3scrim
                    opacity: win.shown ? 0.45 : 0

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: Tokens.spacing.large
                    opacity: win.shown ? 1 : 0
                    scale: win.shown ? 1 : 0.8

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }
                    Behavior on scale {
                        Anim {
                            type: Anim.SlowSpatial
                        }
                    }

                    // The number sits in a shape that keeps changing form behind it.
                    Item {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 220
                        height: 220

                        MaterialShape {
                            id: body

                            readonly property var forms: [MaterialShape.Cookie9Sided, MaterialShape.SoftBurst, MaterialShape.Sunny, MaterialShape.Cookie12Sided, MaterialShape.Pentagon, MaterialShape.Clover4Leaf]
                            property int form

                            anchors.centerIn: parent
                            implicitSize: parent.width
                            shape: forms[(form + win.index) % forms.length]
                            color: Colours.palette.m3primaryContainer
                            animationEasing: Tokens.anim.expressiveFastSpatial
                            animationDuration: Tokens.anim.durations.expressiveDefaultSpatial

                            NumberAnimation on rotation {
                                running: win.shown
                                from: 0
                                to: 360
                                duration: 14000
                                loops: Animation.Infinite
                            }

                            Timer {
                                interval: 900
                                repeat: true
                                running: win.shown
                                onTriggered: body.form++
                            }
                        }

                        StyledText {
                            anchors.centerIn: parent
                            text: String(win.index + 1)
                            font: Tokens.font.headline.builders.large.size(72).weight(Font.Bold).build()
                            color: Colours.palette.m3onPrimaryContainer
                        }
                    }

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: win.modelData.name + (Screens.primaryName === win.modelData.name ? "  ★" : "")
                        font: Tokens.font.headline.large
                        color: Colours.palette.m3onSurface
                    }

                    StyledText {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: win.detail
                        font: Tokens.font.title.medium
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }
            }
        }
    }
}
