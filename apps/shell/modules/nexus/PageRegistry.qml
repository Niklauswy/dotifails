pragma Singleton

import QtQuick
import Wysun.I18n

QtObject {
    id: root

    readonly property list<var> pages: [
        // Appearance
        {
            key: "wallpaper",
            label: Tr.tr("Wallpaper & style"),
            icon: "palette",
            description: Tr.tr("Wallpaper, colours, light and dark"),
            category: "appearance"
        },

        // Connectivity
        {
            key: "network",
            label: Tr.tr("Network"),
            icon: "wifi",
            description: Tr.tr("Wi-Fi, ethernet, VPN"),
            category: "connectivity"
        },
        {
            key: "bluetooth",
            label: Tr.tr("Connected devices"),
            icon: "devices_other",
            description: Tr.tr("Bluetooth, pairing"),
            category: "connectivity",
            noFill: true
        },
        {
            key: "audio",
            label: Tr.tr("Audio"),
            icon: "volume_up",
            description: Tr.tr("App volumes, sound devices"),
            category: "connectivity"
        },

        // Preserve the first four indices used by bar deep links.
        {
            key: "displays",
            label: Tr.tr("Displays"),
            icon: "monitor",
            description: Tr.tr("Arrangement, resolution, scale and refresh rate"),
            category: "connectivity"
        },
        {
            key: "workspaces",
            label: Tr.tr("Workspaces"),
            icon: "view_carousel",
            description: Tr.tr("Workspace assignments by display"),
            category: "shell"
        },
        {
            key: "lock",
            label: Tr.tr("Lock & Idle"),
            icon: "lock_clock",
            description: Tr.tr("Auto-lock, display sleep, lock before sleep"),
            category: "system"
        },
        // System
        {
            key: "updates",
            label: Tr.tr("Updates"),
            icon: "update",
            description: Tr.tr("System updates"),
            category: "system"
        },
        {
            key: "plugins",
            label: Tr.tr("Plugins"),
            icon: "extension",
            description: Tr.tr("Manage plugins"),
            category: "system"
        },

        // Shell
        {
            key: "panels",
            label: Tr.tr("Panels"),
            icon: "dock_to_bottom",
            description: Tr.tr("Dashboard, taskbar, launcher, sidebar"),
            category: "shell"
        },
        {
            key: "apps",
            label: Tr.tr("Apps"),
            icon: "apps",
            description: Tr.tr("Default apps, favourites, hidden apps"),
            category: "shell"
        },
        {
            key: "services",
            label: Tr.tr("Services"),
            icon: "build",
            description: Tr.tr("Poll intervals, lyrics backend"),
            category: "shell"
        },
        {
            key: "language",
            label: Tr.tr("Language & region"),
            icon: "globe",
            description: Tr.tr("UI language, weather location, display units"),
            category: "shell"
        },

        // About
        {
            key: "about",
            label: Tr.tr("About"),
            icon: "info",
            description: Tr.tr("System information, credits"),
            category: "about"
        },


    ]
}
