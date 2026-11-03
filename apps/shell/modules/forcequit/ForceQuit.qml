pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import Wysun.Config
import qs.components
import qs.components.containers
import qs.services
import "ForceQuitLogic.js" as Logic

// The question of Super+Shift+Esc over the active window: the window outlined in the error colour and a compact card
// (Enter forces, Escape cancels). It takes the keyboard only while it is shown.
Scope {
    id: root

    LazyLoader {
        active: ForceQuit.showing

        Variants {
            model: Quickshell.screens.filter(s => s.name === ForceQuit.target?.monitor)

            StyledWindow {
                id: win

                required property ShellScreen modelData
                readonly property var monitor: Hypr.monitorFor(modelData)
                readonly property var t: ForceQuit.target
                readonly property real wx: (t?.at?.[0] ?? 0) - (monitor?.x ?? 0)
                readonly property real wy: (t?.at?.[1] ?? 0) - (monitor?.y ?? 0)
                readonly property var entry: DesktopEntries.heuristicLookup(t?.cls ?? "")

                screen: modelData
                name: "forcequit"
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.exclusionMode: ExclusionMode.Ignore
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

                anchors.top: true
                anchors.bottom: true
                anchors.left: true
                anchors.right: true

                Item {
                    anchors.fill: parent
                    focus: true

                    Keys.onPressed: event => {
                        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            ForceQuit.confirm();
                            event.accepted = true;
                        } else if (event.key === Qt.Key_Escape) {
                            ForceQuit.cancel();
                            event.accepted = true;
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: ForceQuit.cancel()
                    }

                    Rectangle {
                        x: win.wx - Tokens.padding.extraSmall
                        y: win.wy - Tokens.padding.extraSmall
                        width: (win.t?.size?.[0] ?? 0) + Tokens.padding.extraSmall * 2
                        height: (win.t?.size?.[1] ?? 0) + Tokens.padding.extraSmall * 2
                        radius: Tokens.rounding.large
                        color: Qt.alpha(Colours.palette.m3error, 0.08)
                        border.width: Tokens.padding.extraSmall
                        border.color: Colours.palette.m3error
                    }

                    StyledRect {
                        id: card

                        x: win.wx + ((win.t?.size?.[0] ?? 0) - width) / 2
                        y: win.wy + ((win.t?.size?.[1] ?? 0) - height) / 2
                        implicitWidth: Tokens.padding.extraExtraLarge * 8
                        implicitHeight: column.implicitHeight + Tokens.padding.extraLarge * 2
                        radius: Tokens.rounding.extraLarge
                        color: Colours.palette.m3surfaceContainerHigh
                        scale: ForceQuit.showing ? 1 : 0.94

                        Behavior on scale {
                            Anim {
                                type: Anim.DefaultSpatial
                            }
                        }

                        MouseArea {
                            anchors.fill: parent      // clicks inside the card do not cancel
                        }

                        Column {
                            id: column

                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: Tokens.padding.extraLarge
                            spacing: Tokens.spacing.medium

                            Row {
                                spacing: Tokens.spacing.medium

                                StyledRect {
                                    implicitWidth: Tokens.padding.extraExtraLarge
                                    implicitHeight: implicitWidth
                                    radius: Tokens.rounding.large
                                    color: Colours.palette.m3errorContainer

                                    Image {
                                        id: icon

                                        anchors.centerIn: parent
                                        width: parent.width * 0.6
                                        height: width
                                        visible: status === Image.Ready
                                        source: win.entry?.icon ? Quickshell.iconPath(win.entry.icon, true) : ""
                                        sourceSize: Qt.size(width * 2, height * 2)
                                    }

                                    MaterialIcon {
                                        anchors.centerIn: parent
                                        visible: icon.status !== Image.Ready
                                        text: "bolt"
                                        color: Colours.palette.m3onErrorContainer
                                    }
                                }

                                Column {
                                    anchors.verticalCenter: parent.verticalCenter

                                    StyledText {
                                        text: Logic.question(win.entry?.name ?? win.t?.cls ?? "")
                                        font: Tokens.font.title.large
                                    }

                                    StyledText {
                                        width: card.width - Tokens.padding.extraLarge * 2 - Tokens.padding.extraExtraLarge - Tokens.spacing.medium
                                        text: (win.t?.title ?? "") + " · ventana activa"
                                        color: Colours.palette.m3onSurfaceVariant
                                        font: Tokens.font.body.small
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            StyledText {
                                width: parent.width
                                text: "Se detiene al instante, sin guardar."
                                color: Colours.palette.m3onSurfaceVariant
                                font: Tokens.font.body.medium
                                wrapMode: Text.Wrap
                            }

                            Row {
                                anchors.right: parent.right
                                spacing: Tokens.spacing.small

                                StyledRect {
                                    implicitWidth: cancelLabel.implicitWidth + Tokens.padding.large * 2
                                    implicitHeight: cancelLabel.implicitHeight + Tokens.padding.medium * 2
                                    radius: height / 2
                                    color: Colours.palette.m3secondaryContainer

                                    StyledText {
                                        id: cancelLabel

                                        anchors.centerIn: parent
                                        text: "Cancelar · Esc"
                                        color: Colours.palette.m3onSecondaryContainer
                                        font: Tokens.font.label.large
                                    }

                                    StateLayer {
                                        color: Colours.palette.m3onSecondaryContainer
                                        onClicked: ForceQuit.cancel()
                                    }
                                }

                                StyledRect {
                                    implicitWidth: forceLabel.implicitWidth + Tokens.padding.large * 2
                                    implicitHeight: forceLabel.implicitHeight + Tokens.padding.medium * 2
                                    radius: height / 2
                                    color: Colours.palette.m3error

                                    StyledText {
                                        id: forceLabel

                                        anchors.centerIn: parent
                                        text: "Forzar cierre · Enter"
                                        color: Colours.palette.m3onError
                                        font: Tokens.font.label.large
                                    }

                                    StateLayer {
                                        color: Colours.palette.m3onError
                                        onClicked: ForceQuit.confirm()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
