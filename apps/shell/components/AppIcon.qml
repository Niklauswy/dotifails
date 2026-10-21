import QtQuick
import Quickshell
import Quickshell.Widgets
import Wysun.Config
import qs.services

// Desktop-entry icon that never asks the theme for a missing name: when the icon
// theme lacks it, a Material symbol is drawn with the shell's own colours.
Item {
    id: root

    property string name
    property real size: 32

    readonly property var materialFor: ({
            "display": "desktop_windows",
            "video-display": "desktop_windows",
            "preferences-desktop-theme": "palette",
            "preferences-system-network": "lan",
            "network-wireless": "wifi",
            "user-info": "person",
            "system-search": "search",
            "preferences-desktop": "tune",
            "preferences-system": "settings",
            "preferences-system-windows": "web_asset",
            "system-file-manager": "folder"
        })
    readonly property string resolved: name ? Quickshell.iconPath(name, true) : ""

    implicitWidth: size
    implicitHeight: size

    IconImage {
        anchors.fill: parent
        asynchronous: true
        visible: root.resolved !== ""
        source: root.resolved
    }

    MaterialIcon {
        anchors.centerIn: parent
        visible: root.resolved === ""
        text: root.materialFor[root.name] ?? "apps"
        color: Colours.palette.m3onSurfaceVariant
        fontStyle: Tokens.font.icon.builders.large.scale(root.size / 32).build()
    }
}
