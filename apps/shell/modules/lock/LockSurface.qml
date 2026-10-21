pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Mpris
import Quickshell.Services.UPower
import Wysun.Config
import qs.components
import qs.components.controls
import qs.components.images
import qs.services
import qs.utils

// One surface per output. The output that last received input carries the
// identity, password field, status and controls; the others show wallpaper and clock.
WlSessionLockSurface {
    id: root

    required property var lock
    required property Pam pam

    readonly property bool primary: (screen?.name ?? "") === lock.activeScreen
    readonly property real ui: Math.max(0.7, Math.min(2, (screen?.height ?? 1080) / 1080))
    readonly property color fg: Colours.light ? Colours.palette.m3inverseOnSurface : Colours.palette.m3onSurface
    readonly property color fgDim: Qt.alpha(fg, 0.72)
    readonly property color accent: Colours.light ? Colours.palette.m3inversePrimary : Colours.palette.m3primary
    readonly property color glass: Qt.alpha(fg, 0.12)
    readonly property color glassBorder: Qt.alpha(fg, 0.22)
    readonly property bool failed: pam.state === Pam.Failed || pam.state === Pam.Error || pam.state === Pam.MaxTries
    readonly property string message: {
        if (pam.verifying)
            return "Verifying…";
        if (pam.lockMessage)
            return pam.lockMessage;
        if (pam.state === Pam.Error)
            return "Authentication error. Try again.";
        if (pam.state === Pam.MaxTries)
            return "Too many attempts. Try again later.";
        if (pam.state === Pam.Failed)
            return "Incorrect password";
        if (Hypr.capsLock)
            return "Caps Lock is on";
        return "";
    }

    property real enter: 0
    property real leave: 0
    property real shake: 0

    contentItem.Config.screen: screen?.name ?? ""
    contentItem.Tokens.screen: screen?.name ?? ""

    color: Colours.palette.m3surface

    Component.onCompleted: enterAnim.start()

    ParallelAnimation {
        id: enterAnim

        Anim {
            target: root
            property: "enter"
            to: 1
            type: Anim.StandardExtraLarge
            duration: Tokens.anim.durations.extraLarge * 1.4
        }
    }

    Connections {
        function onUnlockingChanged(): void {
            if (root.lock.unlocking)
                leaveAnim.start();
        }

        target: root.lock
    }

    Anim {
        id: leaveAnim

        target: root
        property: "leave"
        to: 1
        type: Anim.StandardLarge
    }

    Connections {
        function onFlashMsg(): void {
            shakeAnim.restart();
        }

        target: root.pam
    }

    SequentialAnimation {
        id: shakeAnim

        NumberAnimation {
            target: root
            property: "shake"
            to: -1
            duration: 50
        }
        NumberAnimation {
            target: root
            property: "shake"
            to: 0.8
            duration: 90
        }
        NumberAnimation {
            target: root
            property: "shake"
            to: -0.55
            duration: 80
        }
        NumberAnimation {
            target: root
            property: "shake"
            to: 0.3
            duration: 70
        }
        NumberAnimation {
            target: root
            property: "shake"
            to: 0
            duration: 60
        }
    }

    // Wallpaper, blurred and darkened.
    Item {
        anchors.fill: parent

        Item {
            anchors.fill: parent
            scale: 1.08 - 0.08 * root.enter + 0.03 * root.leave

            layer.enabled: true
            layer.effect: MultiEffect {
                autoPaddingEnabled: false
                blurEnabled: true
                blur: Math.max(0, root.enter - root.leave * 0.6)
                blurMax: 64
                blurMultiplier: 1
                saturation: -0.15
            }

            CachingImage {
                anchors.fill: parent
                path: Wallpapers.forOutput(root.screen?.name ?? "")
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.alpha(Colours.palette.m3shadow, 0.5 * root.enter)
        }

        Rectangle {
            anchors.fill: parent
            opacity: root.enter

            gradient: Gradient {
                GradientStop {
                    position: 0
                    color: "transparent"
                }
                GradientStop {
                    position: 1
                    color: Qt.alpha(Colours.palette.m3shadow, 0.55)
                }
            }
        }
    }

    // Keys can arrive on any output; the form follows them.
    Item {
        id: keys

        anchors.fill: parent
        focus: true
        Component.onCompleted: forceActiveFocus()
        onActiveFocusChanged: {
            if (!activeFocus)
                forceActiveFocus();
        }

        Keys.onPressed: event => {
            if (root.lock.unlocking)
                return;
            root.lock.activeScreen = root.screen.name;
            root.pam.handleKey(event);
        }

        HoverHandler {
            onHoveredChanged: {
                if (hovered && !root.pam.buffer)
                    root.lock.activeScreen = root.screen.name;
            }
        }
    }

    Item {
        id: stage

        anchors.fill: parent
        opacity: root.enter * (1 - root.leave)
        scale: 1 + 0.025 * root.leave
        transformOrigin: Item.Center

        // Clock + date
        ColumnLayout {
            id: clock

            anchors.horizontalCenter: parent.horizontalCenter
            y: root.primary ? parent.height * 0.1 + (1 - root.enter) * 28 * root.ui : (parent.height - height) / 2
            spacing: 0

            Behavior on y {
                Anim {
                    type: Anim.DefaultSpatial
                }
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                text: `${Time.hourStr}:${Time.minuteStr}${Time.amPmStr ? " " + Time.amPmStr : ""}`
                color: root.fg
                font: Tokens.font.headline.builders.large.scale(root.primary ? 5.2 * root.ui : 7.6 * root.ui).weight(Font.Medium).build()
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                text: Time.format("dddd, d MMMM")
                color: root.fgDim
                font: Tokens.font.title.builders.medium.scale(1.15 * Math.max(0.8, root.ui)).weight(Font.Medium).build()
            }
        }

        // Identity and password
        ColumnLayout {
            id: form

            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.46 + (1 - root.enter) * 40 * root.ui
            spacing: Tokens.spacing.medium * root.ui * 1.4
            visible: opacity > 0
            opacity: root.primary ? 1 : 0

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }

            ProfilePic {
                Layout.alignment: Qt.AlignHCenter
                centerWidth: 300 * root.ui
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                text: root.lock.displayName
                color: root.fg
                font: Tokens.font.title.builders.large.weight(Font.Medium).build()
            }

            // Password field
            StyledRect {
                id: field

                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Tokens.spacing.small * root.ui
                implicitWidth: 380 * root.ui
                implicitHeight: 58 * root.ui
                radius: height / 2
                color: root.glass
                border.width: 2
                border.color: root.failed ? Colours.palette.m3error : keys.activeFocus ? Qt.alpha(root.accent, 0.8) : root.glassBorder

                transform: Translate {
                    x: root.shake * 16 * root.ui
                }

                Behavior on border.color {
                    CAnim {}
                }

                Item {
                    id: lead

                    anchors.left: parent.left
                    anchors.leftMargin: 8 * root.ui
                    anchors.verticalCenter: parent.verticalCenter
                    width: field.height - 16 * root.ui
                    height: width

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: root.failed ? "lock_reset" : "lock"
                        color: root.failed ? Colours.palette.m3error : root.fgDim
                        opacity: root.pam.verifying ? 0 : 1
                        fontStyle: Tokens.font.icon.size(22 * root.ui).build()

                        Behavior on opacity {
                            Anim {
                                type: Anim.FastEffects
                            }
                        }
                    }

                    LoadingIndicator {
                        anchors.centerIn: parent
                        implicitSize: parent.width * 0.8
                        opacity: root.pam.verifying ? 1 : 0

                        Behavior on opacity {
                            Anim {
                                type: Anim.FastEffects
                            }
                        }
                    }
                }

                StyledText {
                    anchors.centerIn: parent
                    text: "Enter password"
                    color: root.fgDim
                    opacity: root.pam.buffer.length === 0 && !root.pam.verifying ? 1 : 0
                    font: Tokens.font.body.builders.medium.scale(1.1).build()

                    Behavior on opacity {
                        Anim {
                            type: Anim.FastEffects
                        }
                    }
                }

                Row {
                    id: dots

                    anchors.centerIn: parent
                    spacing: 9 * root.ui
                    opacity: root.pam.verifying ? 0.45 : 1

                    Behavior on opacity {
                        Anim {
                            type: Anim.FastEffects
                        }
                    }

                    Repeater {
                        model: Math.min(root.pam.buffer.length, 20)

                        Rectangle {
                            width: 11 * root.ui
                            height: width
                            radius: width / 2
                            color: root.failed ? Colours.palette.m3error : root.fg
                            scale: 0

                            Component.onCompleted: scale = 1

                            Behavior on scale {
                                Anim {
                                    type: Anim.FastSpatial
                                }
                            }
                        }
                    }
                }

                // Submit
                StyledRect {
                    anchors.right: parent.right
                    anchors.rightMargin: 8 * root.ui
                    anchors.verticalCenter: parent.verticalCenter
                    width: lead.width
                    height: width
                    radius: width / 2
                    color: root.accent
                    opacity: root.pam.buffer.length > 0 && !root.pam.verifying ? 1 : 0
                    scale: opacity > 0 ? 1 : 0.6

                    Behavior on opacity {
                        Anim {
                            type: Anim.FastEffects
                        }
                    }

                    Behavior on scale {
                        Anim {
                            type: Anim.FastSpatial
                        }
                    }

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: "arrow_forward"
                        color: Colours.on(root.accent)
                        fontStyle: Tokens.font.icon.size(22 * root.ui).build()
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: parent.opacity > 0
                        onClicked: root.pam.submit()
                    }
                }
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredHeight: implicitHeight
                text: root.message
                horizontalAlignment: Text.AlignHCenter
                color: root.failed ? Colours.palette.m3error : root.fgDim
                opacity: text ? 1 : 0
                font: Tokens.font.body.builders.medium.scale(1.05).build()

                Behavior on opacity {
                    Anim {
                        type: Anim.FastEffects
                    }
                }
            }
        }

        // Status chips (bottom left)
        Row {
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: 32 * root.ui
            spacing: 10 * root.ui
            visible: opacity > 0
            opacity: root.primary ? 1 : 0

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }

            Chip {
                visible: UPower.displayDevice.isLaptopBattery
                icon: Icons.getBatteryIcon(UPower.displayDevice.percentage, [UPowerDeviceState.Charging, UPowerDeviceState.FullyCharged, UPowerDeviceState.PendingCharge].includes(UPower.displayDevice.state))
                label: `${Math.round(UPower.displayDevice.percentage * 100)}%`
                warn: UPower.onBattery && UPower.displayDevice.percentage <= 0.2
            }

            Chip {
                icon: Nmcli.activeEthernet ? "cable" : Nmcli.active ? Icons.getNetworkIcon(Nmcli.active.strength ?? 0) : "wifi_off"
                label: Nmcli.activeEthernet ? "Ethernet" : Nmcli.active ? Nmcli.active.ssid : "Offline"
            }

            Chip {
                icon: "keyboard"
                label: Hypr.kbLayout
            }

            Chip {
                visible: Hypr.capsLock
                icon: "keyboard_capslock_badge"
                label: "Caps Lock"
                warn: true
            }
        }

        // Power (bottom centre)
        Row {
            id: power

            property string armed

            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 32 * root.ui
            spacing: 14 * root.ui
            visible: opacity > 0
            opacity: root.primary ? 1 : 0

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }

            Timer {
                id: disarm

                interval: 3000
                onTriggered: power.armed = ""
            }

            Repeater {
                model: [
                    {
                        id: "suspend",
                        icon: "bedtime",
                        label: "Suspend",
                        command: ["systemctl", "suspend"],
                        confirm: false
                    },
                    {
                        id: "reboot",
                        icon: "restart_alt",
                        label: "Restart",
                        command: ["systemctl", "reboot"],
                        confirm: true
                    },
                    {
                        id: "poweroff",
                        icon: "power_settings_new",
                        label: "Shut down",
                        command: ["systemctl", "poweroff"],
                        confirm: true
                    }
                ]

                GlassButton {
                    required property var modelData

                    icon: modelData.icon
                    tooltip: power.armed === modelData.id ? `Click again to ${modelData.label.toLowerCase()}` : modelData.label
                    armed: power.armed === modelData.id
                    onClicked: {
                        if (modelData.confirm && power.armed !== modelData.id) {
                            power.armed = modelData.id;
                            disarm.restart();
                            return;
                        }
                        power.armed = "";
                        Quickshell.execDetached(modelData.command);
                    }
                }
            }
        }

        // Media (bottom right)
        StyledRect {
            id: media

            readonly property MprisPlayer player: Players.active
            readonly property bool shown: root.primary && player !== null && (player.isPlaying || player.playbackState === MprisPlaybackState.Paused) && (player.trackTitle ?? "").length > 0

            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 32 * root.ui
            implicitWidth: 340 * root.ui
            implicitHeight: 84 * root.ui
            radius: Tokens.rounding.large
            color: root.glass
            border.width: 1
            border.color: root.glassBorder
            visible: opacity > 0
            opacity: shown ? 1 : 0

            Behavior on opacity {
                Anim {
                    type: Anim.DefaultEffects
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12 * root.ui
                spacing: 12 * root.ui

                StyledRect {
                    Layout.preferredWidth: media.height - 24 * root.ui
                    Layout.preferredHeight: Layout.preferredWidth
                    radius: Tokens.rounding.small
                    color: Qt.alpha(root.fg, 0.1)
                    clip: true

                    MaterialIcon {
                        anchors.centerIn: parent
                        text: "music_note"
                        color: root.fgDim
                    }

                    FadeImage {
                        anchors.fill: parent
                        source: Players.getArtUrl(media.player)
                        asynchronous: true
                        fillMode: Image.PreserveAspectCrop
                        opacity: status === Image.Ready ? 1 : 0
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    StyledText {
                        Layout.fillWidth: true
                        text: media.player?.trackTitle ?? ""
                        color: root.fg
                        elide: Text.ElideRight
                        font: Tokens.font.title.builders.small.weight(Font.Medium).build()
                    }

                    StyledText {
                        Layout.fillWidth: true
                        text: media.player?.trackArtist ?? ""
                        color: root.fgDim
                        elide: Text.ElideRight
                        font: Tokens.font.body.medium
                    }
                }

                RowLayout {
                    spacing: 2 * root.ui

                    MediaKey {
                        icon: "skip_previous"
                        enabled: media.player?.canGoPrevious ?? false
                        onClicked: media.player.previous()
                    }

                    MediaKey {
                        icon: media.player?.isPlaying ? "pause" : "play_arrow"
                        enabled: media.player?.canTogglePlaying ?? false
                        onClicked: media.player.togglePlaying()
                    }

                    MediaKey {
                        icon: "skip_next"
                        enabled: media.player?.canGoNext ?? false
                        onClicked: media.player.next()
                    }
                }
            }
        }
    }

    component Chip: StyledRect {
        id: chip

        property string icon
        property string label
        property bool warn

        implicitWidth: chipRow.implicitWidth + 24 * root.ui
        implicitHeight: 38 * root.ui
        radius: height / 2
        color: root.glass
        border.width: 1
        border.color: chip.warn ? Colours.palette.m3error : root.glassBorder

        Row {
            id: chipRow

            anchors.centerIn: parent
            spacing: 7 * root.ui

            MaterialIcon {
                anchors.verticalCenter: parent.verticalCenter
                text: chip.icon
                color: chip.warn ? Colours.palette.m3error : root.fg
                fontStyle: Tokens.font.icon.size(19 * root.ui).build()
            }

            StyledText {
                anchors.verticalCenter: parent.verticalCenter
                text: chip.label
                color: chip.warn ? Colours.palette.m3error : root.fg
                font: Tokens.font.label.builders.large.scale(Math.max(0.9, root.ui)).build()
            }
        }
    }

    component GlassButton: StyledRect {
        id: button

        property string icon
        property string tooltip
        property bool armed

        signal clicked

        implicitWidth: 52 * root.ui
        implicitHeight: implicitWidth
        radius: armed ? Tokens.rounding.large : height / 2
        color: armed ? Colours.palette.m3error : mouse.containsMouse ? Qt.alpha(root.fg, 0.24) : root.glass
        border.width: 1
        border.color: armed ? Colours.palette.m3error : root.glassBorder
        scale: mouse.pressed ? 0.92 : 1

        Behavior on scale {
            Anim {
                type: Anim.FastSpatial
            }
        }

        Behavior on radius {
            Anim {
                type: Anim.FastSpatial
            }
        }

        MaterialIcon {
            anchors.centerIn: parent
            text: button.icon
            color: button.armed ? Colours.palette.m3onError : root.fg
            fontStyle: Tokens.font.icon.size(24 * root.ui).build()
        }

        MouseArea {
            id: mouse

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.clicked()
        }

        StyledRect {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.top
            anchors.bottomMargin: 10 * root.ui
            implicitWidth: tip.implicitWidth + 20 * root.ui
            implicitHeight: tip.implicitHeight + 10 * root.ui
            radius: height / 2
            color: Qt.alpha(Colours.palette.m3shadow, 0.65)
            opacity: mouse.containsMouse || button.armed ? 1 : 0

            Behavior on opacity {
                Anim {
                    type: Anim.FastEffects
                }
            }

            StyledText {
                id: tip

                anchors.centerIn: parent
                text: button.tooltip
                color: root.fg
                font: Tokens.font.label.medium
            }
        }
    }

    component MediaKey: Item {
        id: key

        property string icon
        signal clicked

        implicitWidth: 36 * root.ui
        implicitHeight: implicitWidth
        opacity: enabled ? 1 : 0.35

        MaterialIcon {
            anchors.centerIn: parent
            text: key.icon
            color: root.fg
            fill: 1
            fontStyle: Tokens.font.icon.size(26 * root.ui).build()
            scale: keyMouse.pressed ? 0.85 : keyMouse.containsMouse ? 1.12 : 1

            Behavior on scale {
                Anim {
                    type: Anim.FastSpatial
                }
            }
        }

        MouseArea {
            id: keyMouse

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: key.clicked()
        }
    }
}
