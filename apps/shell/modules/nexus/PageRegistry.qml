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
            description: Tr.tr("Wallpaper, fonts, colours"),
            category: "appearance"
        },

        // Connectivity
        // TODO
        // {
        //     label: Tr.tr("Display"),
        //     icon: "monitor",
        //     description: Tr.tr("Output configuration"),
        //     category: "connectivity"
        // },
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
        {
            key: "ssh",
            label: "SSH",
            icon: "terminal",
            description: "Servidores y accesos remotos",
            category: "connectivity"
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
        {
            key: "processes",
            label: "Procesos",
            icon: "monitor_heart",
            description: "CPU, memoria y control de procesos",
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

        // The bar's deep links only use the first four pages; keep those first.
        {
            key: "desktop",
            label: Tr.tr("Escritorio"),
            icon: "desktop_windows",
            description: Tr.tr("Pantallas, atajos, reglas, inicio y copias"),
            category: "desktop"
        },
    ]
}
