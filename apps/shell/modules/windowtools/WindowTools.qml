pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services
import "../../services/WindowToolsLogic.js" as Logic

// Draws what services/WindowTools asks for: the locate halo (on the monitor that shows the window; elsewhere a
// capsule with «Ir») and the thumbnail captures, made in an invisible item of the first screen's window. The windows
// let clicks through except over the capsule, take no keyboard focus and exist only while needed.
Scope {
    id: root

    LazyLoader {
        active: WindowTools.alive

        Variants {
            model: Quickshell.screens

            StyledWindow {
                id: win

                required property ShellScreen modelData
                readonly property var monitor: Hypr.monitorFor(modelData)
                readonly property var target: WindowTools.target
                readonly property var ipc: target?.lastIpcObject ?? null
                readonly property int targetWs: target?.workspace?.id ?? -1
                readonly property var place: Logic.placement(ipc, monitor ? {name: monitor.name, x: monitor.x, y: monitor.y, width: monitor.width, height: monitor.height} : null,
                                                             {name: modelData.name, activeWs: monitor?.activeWorkspace?.id ?? -1}, targetWs)
                readonly property bool here: WindowTools.showing && place.visible
                readonly property bool capsule: WindowTools.showing && !anyHere() && modelData === Quickshell.screens[0]

                function anyHere() {
                    for (const s of Quickshell.screens) {
                        const m = Hypr.monitorFor(s);
                        if (m && target && m.name === target.monitor?.name && m.activeWorkspace?.id === targetWs)
                            return true;
                    }
                    return false;
                }

                screen: modelData
                name: "windowtools"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                mask: Region {
                    item: win.capsule ? pill : null
                }

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                // Dim everything but the window.
                Item {
                    anchors.fill: parent
                    opacity: win.here ? 1 : 0

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }

                    Rectangle { x: 0; y: 0; width: parent.width; height: win.place.y; color: Qt.alpha(Colours.palette.m3scrim, 0.5) }
                    Rectangle { x: 0; y: win.place.y + win.place.height; width: parent.width; height: parent.height - y; color: Qt.alpha(Colours.palette.m3scrim, 0.5) }
                    Rectangle { x: 0; y: win.place.y; width: win.place.x; height: win.place.height; color: Qt.alpha(Colours.palette.m3scrim, 0.5) }
                    Rectangle { x: win.place.x + win.place.width; y: win.place.y; width: parent.width - x; height: win.place.height; color: Qt.alpha(Colours.palette.m3scrim, 0.5) }
                }

                // The halo: an accent border with a soft ring that breathes.
                Item {
                    x: win.place.x
                    y: win.place.y
                    width: win.place.width
                    height: win.place.height
                    opacity: win.here ? 1 : 0
                    scale: win.here ? 1 : 1.04

                    Behavior on opacity {
                        Anim {
                            type: Anim.DefaultEffects
                        }
                    }
                    Behavior on scale {
                        Anim {
                            type: Anim.DefaultSpatial
                        }
                    }

                    Rectangle {
                        id: ring

                        anchors.fill: parent
                        anchors.margins: -Tokens.padding.large
                        radius: Tokens.rounding.extraLarge
                        color: "transparent"
                        border.width: Tokens.padding.small
                        border.color: Qt.alpha(Colours.palette.m3primary, 0.35)

                        SequentialAnimation on anchors.margins {
                            running: win.here
                            loops: Animation.Infinite
                            NumberAnimation { to: -Tokens.padding.extraLarge; duration: Tokens.anim.durations.large; easing: Tokens.anim.standard }
                            NumberAnimation { to: -Tokens.padding.large; duration: Tokens.anim.durations.large; easing: Tokens.anim.standard }
                        }
                    }

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -Tokens.padding.extraSmall
                        radius: Tokens.rounding.large
                        color: "transparent"
                        border.width: Tokens.padding.extraSmall
                        border.color: Colours.palette.m3primary
                    }
                }

                // Elsewhere: a capsule with the workspace and «Ir».
                Rectangle {
                    id: pill

                    anchors.horizontalCenter: parent.horizontalCenter
                    y: win.capsule ? Tokens.padding.extraLarge * 2 : -height
                    width: pillRow.implicitWidth + Tokens.padding.large * 2
                    height: pillRow.implicitHeight + Tokens.padding.medium * 2
                    radius: height / 2
                    color: Colours.palette.m3surfaceContainerHigh
                    visible: y > -height

                    Behavior on y {
                        Anim {
                            type: Anim.DefaultSpatial
                        }
                    }

                    Row {
                        id: pillRow

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.medium

                        MaterialIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "my_location"
                            color: Colours.palette.m3primary
                        }

                        StyledText {
                            anchors.verticalCenter: parent.verticalCenter
                            text: Logic.elsewhere(win.ipc?.class ?? WindowTools.targetLabel, win.targetWs)
                            font: Tokens.font.body.medium
                        }

                        StyledRect {
                            anchors.verticalCenter: parent.verticalCenter
                            implicitWidth: goLabel.implicitWidth + Tokens.padding.large * 2
                            implicitHeight: goLabel.implicitHeight + Tokens.padding.small * 2
                            radius: height / 2
                            color: Colours.palette.m3primary

                            StyledText {
                                id: goLabel

                                anchors.centerIn: parent
                                text: "Ir"
                                color: Colours.palette.m3onPrimary
                                font: Tokens.font.label.large
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: WindowTools.focusTarget()
                            }
                        }
                    }
                }

                // Thumbnail captures: rendered into images by grabToImage, never shown (opacity 0).
                Item {
                    visible: win.modelData === Quickshell.screens[0]
                    opacity: 0

                    Repeater {
                        model: win.modelData === Quickshell.screens[0] && WindowTools.capturing ? WindowTools.pending : []

                        ScreencopyView {
                            id: shot

                            required property string modelData
                            readonly property var toplevel: WindowTools.toplevel(modelData)
                            property int done: -1

                            width: 480
                            height: toplevel?.lastIpcObject?.size ? Math.round(480 * toplevel.lastIpcObject.size[1] / Math.max(1, toplevel.lastIpcObject.size[0])) : 270
                            captureSource: toplevel?.wayland ?? null
                            live: false

                            function grab() {
                                if (!hasContent || done === WindowTools.generation)
                                    return;
                                done = WindowTools.generation;
                                const path = Logic.thumbPath(WindowTools.runtimeDir, modelData);
                                grabToImage(result => {
                                    if (result.saveToFile(path))
                                        WindowTools.captured(modelData, path);
                                }, Qt.size(width, height));
                            }

                            onHasContentChanged: grab()
                            Component.onCompleted: grab()

                            Connections {
                                target: WindowTools

                                function onGenerationChanged() {
                                    shot.captureFrame();
                                    Qt.callLater(shot.grab);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
