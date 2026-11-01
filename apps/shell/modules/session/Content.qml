pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Wysun
import Wysun.Config
import Wysun.Services
import qs.components
import qs.components.controls
import qs.components.widgets
import qs.services
import qs.utils
import "../../utils/Uptime.js" as Uptime

Column {
    id: root

    required property ScreenState screenState

    padding: Tokens.padding.large
    rightPadding: CUtils.clamp(padding - Config.border.thickness, 0, padding)
    spacing: Tokens.spacing.large

    // The time, hours over minutes like the bar's clock, and how long the computer has been on.
    StyledRect {
        implicitWidth: Tokens.sizes.session.button
        implicitHeight: info.implicitHeight
        radius: Tokens.rounding.largeIncreased
        color: Colours.tPalette.m3surfaceContainer

        Column {
            id: info

            width: parent.width
            topPadding: Tokens.padding.medium
            bottomPadding: Tokens.padding.medium
            spacing: 0

            StyledText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Time.hourStr
                font: Tokens.font.headline.builders.medium.weight(Font.Medium).build()
            }

            StyledText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: Time.minuteStr
                color: Colours.palette.m3primary
                font: Tokens.font.headline.builders.medium.weight(Font.Medium).build()
            }

            StyledText {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: !!Time.amPmStr
                text: Time.amPmStr
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.label.small
            }

            StyledRect {
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width - Tokens.padding.large * 2
                height: 1
                color: Colours.palette.m3outlineVariant
                opacity: 0.6
            }

            MaterialIcon {
                anchors.horizontalCenter: parent.horizontalCenter
                topPadding: Tokens.padding.small
                text: "timer"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.small
            }

            Repeater {
                model: Uptime.compact(SysInfo.uptimeSeconds)

                StyledText {
                    required property string modelData

                    anchors.horizontalCenter: parent.horizontalCenter
                    text: modelData
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.label.medium
                }
            }
        }
    }

    // Power, lock, restart and suspend: no logout or hibernate. Focus starts on the safest one.
    SessionButton {
        id: shutdown

        icon: Config.session.icons.shutdown
        command: Config.session.commands.shutdown

        KeyNavigation.down: lock
    }

    SessionButton {
        id: lock

        icon: "lock"
        command: ["wysun-lock"]

        KeyNavigation.up: shutdown
        KeyNavigation.down: reboot

        Component.onCompleted: forceActiveFocus()

        Connections {
            function onLauncherChanged(): void {
                if (!root.screenState.launcher)
                    lock.forceActiveFocus();
            }

            target: root.screenState
        }
    }

    // The waffle's little story (components/widgets/Waffle.qml), in the theme's colours.
    Waffle {
        width: Tokens.sizes.session.button
        height: Tokens.sizes.session.button
        act: "story"
    }

    SessionButton {
        id: reboot

        icon: Config.session.icons.reboot
        command: Config.session.commands.reboot

        KeyNavigation.up: lock
        KeyNavigation.down: suspend
    }

    SessionButton {
        id: suspend

        icon: "bedtime"
        command: ["systemctl", "suspend"]

        KeyNavigation.up: reboot
    }

    component SessionButton: IconButton {
        id: button

        required property list<string> command

        function exec(): void {
            if (!SessionManager.exec(command))
                Quickshell.execDetached(command);
        }

        implicitWidth: Tokens.sizes.session.button
        implicitHeight: Tokens.sizes.session.button

        inactiveColour: activeFocus ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
        inactiveOnColour: activeFocus ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
        radius: pressed ? Tokens.rounding.medium : activeFocus ? Tokens.rounding.extraLarge : Tokens.rounding.largeIncreased
        font: Tokens.font.icon.builders.large.scale(1.3).build()
        onClicked: exec()

        Keys.onEnterPressed: exec()
        Keys.onReturnPressed: exec()
        Keys.onEscapePressed: root.screenState.session = false
        Keys.onPressed: event => {
            if (!Config.session.vimKeybinds)
                return;

            if (event.modifiers & Qt.ControlModifier) {
                if ((event.key === Qt.Key_J || event.key === Qt.Key_N) && KeyNavigation.down) {
                    KeyNavigation.down.focus = true;
                    event.accepted = true;
                } else if ((event.key === Qt.Key_K || event.key === Qt.Key_P) && KeyNavigation.up) {
                    KeyNavigation.up.focus = true;
                    event.accepted = true;
                }
            } else if (event.key === Qt.Key_Tab && KeyNavigation.down) {
                KeyNavigation.down.focus = true;
                event.accepted = true;
            } else if (event.key === Qt.Key_Backtab || (event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier))) {
                if (KeyNavigation.up) {
                    KeyNavigation.up.focus = true;
                    event.accepted = true;
                }
            }
        }
    }
}
