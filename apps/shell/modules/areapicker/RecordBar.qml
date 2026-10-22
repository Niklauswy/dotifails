pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Wysun.Config
import Wysun.I18n
import qs.components
import qs.components.effects
import qs.services

// What to record in a selected region: start, microphone, system audio, cursor or cancel.
StyledRect {
    id: root

    property bool mic
    property bool system
    property bool cursor
    property bool camera
    // Which device list is open above the bar: "", "mic" or "camera".
    property string menu

    signal start
    signal toggleMic
    signal toggleSystem
    signal toggleCursor
    signal toggleCamera
    signal cancel

    implicitWidth: row.implicitWidth + Tokens.padding.small * 2
    implicitHeight: row.implicitHeight + Tokens.padding.small * 2
    radius: Tokens.rounding.full
    color: Colours.palette.m3surfaceContainer
    border.width: 1
    border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)

    Elevation {
        anchors.fill: parent
        radius: root.radius
        level: 3
        z: -1
    }

    RowLayout {
        id: row

        anchors.centerIn: parent
        spacing: Tokens.spacing.extraSmall

        Option {
            primary: true
            icon: "screen_record"
            text: Tr.tr("Record")
            key: "↵"
            onClicked: root.start()
        }

        StyledRect {
            Layout.preferredWidth: 1
            Layout.preferredHeight: Tokens.spacing.large
            color: Colours.palette.m3outlineVariant
        }

        Option {
            icon: root.mic ? "mic" : "mic_off"
            text: root.mic && Recorder.micName ? Recorder.micName : Tr.tr("Microphone")
            maxTextWidth: 170
            key: "M"
            checked: root.mic
            more: Recorder.mics.length > 0
            moreOpen: root.menu === "mic"
            onClicked: root.toggleMic()
            onMoreClicked: root.menu = root.menu === "mic" ? "" : "mic"
        }

        Option {
            icon: root.system ? "volume_up" : "volume_off"
            text: Tr.tr("System audio")
            key: "S"
            checked: root.system
            onClicked: root.toggleSystem()
        }

        Option {
            icon: "arrow_selector_tool"
            text: Tr.tr("Cursor")
            key: "C"
            checked: root.cursor
            onClicked: root.toggleCursor()
        }

        Option {
            icon: root.camera ? "videocam" : "videocam_off"
            text: Tr.tr("Camera")
            key: "V"
            checked: root.camera
            enabled: Recorder.cameras.length > 0
            more: Recorder.cameras.length > 0
            moreOpen: root.menu === "camera"
            onClicked: root.toggleCamera()
            onMoreClicked: root.menu = root.menu === "camera" ? "" : "camera"
        }

        StyledRect {
            Layout.preferredWidth: 1
            Layout.preferredHeight: Tokens.spacing.large
            color: Colours.palette.m3outlineVariant
        }

        Option {
            icon: "close"
            key: "Esc"
            onClicked: root.cancel()
        }
    }

    // Devices of the open option, above the bar.
    StyledRect {
        id: popup

        readonly property var entries: root.menu === "mic" ? Recorder.mics : root.menu === "camera" ? Recorder.cameras : []

        visible: root.menu !== "" && entries.length > 0
        opacity: visible ? 1 : 0
        anchors.bottom: parent.top
        anchors.bottomMargin: Tokens.spacing.small
        anchors.horizontalCenter: parent.horizontalCenter
        implicitWidth: Math.max(260, list.implicitWidth + Tokens.padding.small * 2)
        implicitHeight: list.implicitHeight + Tokens.padding.small * 2 + (root.menu === "camera" ? corners.implicitHeight + Tokens.padding.small : 0)
        radius: Tokens.rounding.large
        color: Colours.palette.m3surfaceContainer
        border.width: 1
        border.color: Qt.alpha(Colours.palette.m3outlineVariant, 0.6)
        scale: visible ? 1 : 0.92
        transformOrigin: Item.Bottom

        Behavior on opacity {
            Anim {}
        }

        Behavior on scale {
            Anim {}
        }

        Elevation {
            anchors.fill: parent
            radius: popup.radius
            level: 3
            z: -1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Tokens.padding.small
            spacing: Tokens.padding.small

            ColumnLayout {
                id: list

                Layout.fillWidth: true
                spacing: 2

                Repeater {
                    model: popup.entries

                    StyledRect {
                        id: entry

                        required property var modelData
                        readonly property bool current: root.menu === "mic" ? (Recorder.micDevice ? Recorder.micDevice === modelData.id : modelData.default) : (Recorder.cameraDevice ? Recorder.cameraDevice === modelData.id : modelData.id === Recorder.cameras[0]?.id)

                        Layout.fillWidth: true
                        implicitWidth: label.implicitWidth + Tokens.padding.large * 2 + Tokens.spacing.extraLarge
                        implicitHeight: label.implicitHeight + Tokens.padding.small * 2
                        radius: Tokens.rounding.medium
                        color: current ? Colours.palette.m3secondaryContainer : "transparent"

                        StateLayer {
                            radius: entry.radius
                            color: entry.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                            onClicked: {
                                Recorder.setPref(root.menu === "mic" ? "record_mic_device" : "camera_device", entry.modelData.id);
                                if (root.menu === "mic" && !root.mic)
                                    root.toggleMic();
                                if (root.menu === "camera" && !root.camera)
                                    root.toggleCamera();
                                root.menu = "";
                            }
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Tokens.padding.medium
                            anchors.rightMargin: Tokens.padding.medium
                            spacing: Tokens.spacing.small

                            MaterialIcon {
                                text: entry.current ? "radio_button_checked" : "radio_button_unchecked"
                                color: entry.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                                fontStyle: Tokens.font.icon.medium
                            }

                            StyledText {
                                id: label

                                Layout.fillWidth: true
                                text: entry.modelData.name
                                elide: Text.ElideRight
                                color: entry.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                            }
                        }
                    }
                }
            }

            // Where the camera sits in the video.
            RowLayout {
                id: corners

                visible: root.menu === "camera"
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall

                StyledText {
                    Layout.fillWidth: true
                    Layout.leftMargin: Tokens.padding.medium
                    text: Tr.tr("Corner")
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.label.small
                }

                Repeater {
                    model: [
                        { id: "top-left", icon: "north_west" },
                        { id: "top-right", icon: "north_east" },
                        { id: "bottom-left", icon: "south_west" },
                        { id: "bottom-right", icon: "south_east" }
                    ]

                    StyledRect {
                        id: corner

                        required property var modelData
                        readonly property bool current: Recorder.cameraStyle.corner === modelData.id

                        implicitWidth: Tokens.spacing.extraLarge + Tokens.padding.small
                        implicitHeight: implicitWidth
                        radius: Tokens.rounding.full
                        color: current ? Colours.palette.m3secondaryContainer : "transparent"

                        StateLayer {
                            radius: corner.radius
                            color: corner.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                            onClicked: Recorder.setPref("camera_corner", corner.modelData.id)
                        }

                        MaterialIcon {
                            anchors.centerIn: parent
                            text: corner.modelData.icon
                            color: corner.current ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                            fontStyle: Tokens.font.icon.medium
                        }
                    }
                }
            }
        }
    }

    component Option: StyledRect {
        id: option

        property string icon
        property string text
        property string key
        property bool primary
        property bool checked
        property bool more
        property bool moreOpen
        property real maxTextWidth: 0
        readonly property color fg: primary ? Colours.palette.m3onPrimary : checked ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface

        signal clicked
        signal moreClicked

        opacity: enabled ? 1 : 0.38
        implicitWidth: content.implicitWidth + Tokens.padding.medium * 2 + (more ? chevron.width : 0)
        implicitHeight: content.implicitHeight + Tokens.padding.small * 2
        radius: Tokens.rounding.full
        color: primary ? Colours.palette.m3primary : checked ? Colours.palette.m3secondaryContainer : "transparent"

        StateLayer {
            anchors.rightMargin: option.more ? chevron.width : 0
            radius: option.radius
            color: option.fg
            disabled: !option.enabled
            onClicked: option.clicked()
        }

        // Opens the list of devices for this option.
        StyledRect {
            id: chevron

            visible: option.more
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: Tokens.spacing.extraLarge
            radius: Tokens.rounding.full
            color: "transparent"

            StateLayer {
                radius: chevron.radius
                color: option.fg
                disabled: !option.enabled
                onClicked: option.moreClicked()
            }

            MaterialIcon {
                anchors.centerIn: parent
                text: "expand_less"
                rotation: option.moreOpen ? 180 : 0
                color: option.fg
                fontStyle: Tokens.font.icon.small

                Behavior on rotation {
                    Anim {}
                }
            }
        }

        RowLayout {
            id: content

            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: Tokens.padding.medium
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: option.icon
                color: option.fg
                fontStyle: Tokens.font.icon.medium
            }

            StyledText {
                visible: option.text.length > 0
                text: option.text
                font: Tokens.font.label.builders.large.weight(Font.Medium).build()
                color: option.fg
                elide: Text.ElideRight
                Layout.maximumWidth: option.maxTextWidth > 0 ? option.maxTextWidth : implicitWidth
            }

            StyledRect {
                implicitWidth: keycap.implicitWidth + Tokens.padding.small
                implicitHeight: keycap.implicitHeight + Tokens.padding.extraSmall / 2
                radius: Tokens.rounding.extraSmall
                color: option.primary ? Qt.alpha(Colours.palette.m3onPrimary, 0.18) : Colours.palette.m3surfaceContainerHighest

                StyledText {
                    id: keycap

                    anchors.centerIn: parent
                    text: option.key
                    font: Tokens.font.label.small
                    color: option.primary ? Colours.palette.m3onPrimary : Colours.palette.m3onSurfaceVariant
                }
            }
        }
    }
}
