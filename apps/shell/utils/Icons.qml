pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import Wysun.Config

Singleton {
    id: root

    readonly property var weatherIcons: ({
            "0": "clear_day",
            "1": "clear_day",
            "2": "partly_cloudy_day",
            "3": "cloud",
            "45": "foggy",
            "48": "foggy",
            "51": "rainy",
            "53": "rainy",
            "55": "rainy",
            "56": "rainy",
            "57": "rainy",
            "61": "rainy",
            "63": "rainy",
            "65": "rainy",
            "66": "rainy",
            "67": "rainy",
            "71": "cloudy_snowing",
            "73": "cloudy_snowing",
            "75": "snowing_heavy",
            "77": "cloudy_snowing",
            "80": "rainy",
            "81": "rainy",
            "82": "rainy",
            "85": "cloudy_snowing",
            "86": "snowing_heavy",
            "95": "thunderstorm",
            "96": "thunderstorm",
            "99": "thunderstorm"
        })

    readonly property var categoryIcons: ({
            WebBrowser: "web",
            Printing: "print",
            Security: "security",
            Network: "chat",
            Archiving: "archive",
            Compression: "archive",
            Development: "code",
            IDE: "code",
            TextEditor: "edit_note",
            Audio: "music_note",
            Music: "music_note",
            Player: "music_note",
            Recorder: "mic",
            Game: "sports_esports",
            FileTools: "files",
            FileManager: "files",
            Filesystem: "files",
            FileTransfer: "files",
            Settings: "settings",
            DesktopSettings: "settings",
            HardwareSettings: "settings",
            TerminalEmulator: "terminal",
            ConsoleOnly: "terminal",
            Utility: "build",
            Monitor: "monitor_heart",
            Midi: "graphic_eq",
            Mixer: "graphic_eq",
            AudioVideoEditing: "video_settings",
            AudioVideo: "music_video",
            Video: "videocam",
            Building: "construction",
            Graphics: "photo_library",
            "2DGraphics": "photo_library",
            RasterGraphics: "photo_library",
            TV: "tv",
            System: "host",
            Office: "content_paste"
        })

    // qmlformat off
    readonly property list<string> networkIcons: [
        "signal_wifi_0_bar",
        "network_wifi_1_bar",
        "network_wifi_2_bar",
        "network_wifi_3_bar",
        "network_wifi"
    ]

    readonly property var bluetoothIconRules: [
        [["headset", "headphones"], "headphones"],
        [["audio"], "speaker"],
        [["phone"], "smartphone"],
        [["mouse"], "mouse"],
        [["keyboard"], "keyboard"]
    ]

    readonly property var notifIconRules: [
        [["reboot"], "restart_alt"],
        [["recording"], "screen_record"],
        [["battery"], "power"],
        [["screenshot"], "screenshot_monitor"],
        [["welcome"], "waving_hand"],
        [["time", "a break"], "schedule"],
        [["installed"], "download"],
        [["update"], "update"],
        [["unable to"], "deployed_code_alert"],
        [["profile"], "person"],
        [["file"], "folder_copy"]
    ]
    // qmlformat on

    /**
     * Checks if a name matches an icon rule. See the IconRule type in the config module.
     */
    function matchIconRule(name: string, iconRule: var): bool {
        if (!iconRule.icon)
            return false;

        if (iconRule.regex) {
            const re = new RegExp(iconRule.regex, iconRule.flags ?? "");
            if (re.test(name))
                return true;
        } else if (iconRule.name === name) {
            return true;
        }

        return false;
    }

    function matchIconRuleList(name: string, rules: var): string {
        if (!rules)
            return "";

        for (const iconRule of rules.values)
            if (matchIconRule(name, iconRule))
                return iconRule.icon;

        return "";
    }

    function getAppIcon(name: string, fallback: string): string {
        const icon = DesktopEntries.heuristicLookup(name)?.icon;
        if (fallback !== "undefined")
            return Quickshell.iconPath(icon, fallback);
        return Quickshell.iconPath(icon);
    }

    function getAppCategoryIcon(name: string, fallback: string): string {
        const match = matchIconRuleList(name, GlobalConfig.bar.workspaces.windowIcons);
        if (match)
            return match;

        const categories = DesktopEntries.heuristicLookup(name)?.categories;
        if (categories)
            for (const [key, value] of Object.entries(categoryIcons))
                if (categories.includes(key))
                    return value;

        return fallback;
    }

    /**
     * Accepts a list of tables containing matching rules (strings) and their corresponding results.
     * If any of the strings are found in the text, returns the result associated with them. Otherwise returns the fallback.
     */
    function matchIcon(text: string, rules: var, fallback: string): string {
        for (const [needles, result] of rules)
            if (needles.some(n => text.includes(n)))
                return result;

        return fallback;
    }

    function getNetworkIcon(strength: int, isSecure = false): string {
        const level = Math.max(0, Math.min(4, Math.floor(strength / 20)));
        const icon = networkIcons[level];

        return isSecure && level > 0 ? `${icon}_locked` : icon;
    }

    function getBluetoothIcon(icon: string): string {
        return matchIcon(icon, bluetoothIconRules, "bluetooth");
    }

    function getWeatherIcon(code: string): string {
        return weatherIcons[code] ?? "air";
    }

    readonly property var notifSymbolRules: [
        [["mail", "email", "correo", "inbox", "gmail", "thunderbird"], "mail"],
        [["battery", "bater", "charger", "charging", "cargador", "low power"], "battery_alert"],
        [["download", "descarg"], "download"],
        [["upload", "subid", "subiendo"], "upload"],
        [["music", "audio", "player", "spotify", "reprodu", "sound", "volume", "podcast"], "music_note"],
        [["video", "movie", "film", "camera", "webcam"], "movie"],
        [["screenshot", "captura", "record", "grab"], "screenshot"],
        [["terminal", "compil", "build", "shell", "console", "git"], "terminal"],
        [["calendar", "appointment", "reuni", "event", "agenda", "cita"], "event"],
        [["update", "actualiz", "upgrade", "install", "package", "apt"], "system_update"],
        [["wifi", "network", "red ", "ethernet", "vpn", "connection", "conexi"], "wifi"],
        [["bluetooth"], "bluetooth"],
        [["usb", "disk", "drive", "mount", "storage", "disco"], "usb"],
        [["folder", "file", "archivo", "carpeta", "document"], "folder"],
        [["chat", "message", "mensaje", "telegram", "whatsapp", "discord", "signal", "slack", "sms"], "chat"],
        [["weather", "clima", "rain", "lluvia"], "partly_cloudy_day"],
        [["timer", "alarm", "reloj", "clock", "recordatorio", "reminder"], "alarm"],
        [["error", "fail", "fallo", "falló", "crash", "denied"], "error"],
        [["warning", "alert", "alerta", "aviso", "cuidado"], "warning"],
        [["done", "listo", "complet", "success", "éxito", "exito", "ok "], "check_circle"],
        [["info", "tip", "help", "ayuda"], "info"]
    ]

    // Icon names for apps whose notifications use a different name than their desktop entry.
    readonly property var appIconAliases: ({
            "claude": "claude-desktop",
            "brave": "brave-browser",
            "chrome": "google-chrome",
            "firefox": "firefox",
            "telegram": "org.telegram.desktop",
            "ghostty": "com.mitchellh.ghostty"
        })

    // Real icon file of an app: the notification's own icon, its desktop entry (hint or heuristic name match), or a known alias.
    function appIconPath(icon: string, app: string, hints: var): string {
        const names = [icon];
        const entryId = hints?.["desktop-entry"];
        if (entryId)
            names.push(DesktopEntries.byId(entryId)?.icon ?? "");
        if (app)
            names.push(DesktopEntries.heuristicLookup(app)?.icon ?? "");
        const lowered = (app ?? "").toLowerCase();
        for (const key of Object.keys(appIconAliases))
            if (lowered.includes(key))
                names.push(appIconAliases[key]);
        for (const name of names) {
            if (!name)
                continue;
            if (name.startsWith("/") || name.startsWith("file:"))
                return name;
            const path = Quickshell.iconPath(name, true);
            if (path)
                return path;
        }
        return "";
    }

    // Notification pictures may point at an icon the theme lacks (drawn as a magenta checkerboard): drop those.
    function usableImage(url: string): string {
        if (url && url.startsWith("image://icon/") && !Quickshell.iconPath(url.slice(13), true))
            return "";
        return url ?? "";
    }

    // One Material symbol for a notification: looks at the app's icon name, its app name and the summary.
    function notifSymbol(icon: string, app: string, summary: string, urgency: int): string {
        const text = `${icon} ${app} ${summary}`.toLowerCase();
        for (const [needles, symbol] of notifSymbolRules)
            if (needles.some(n => text.includes(n)))
                return symbol;
        // Unknown apps get no symbol: the card shows their initial instead of a generic bell.
        return urgency === NotificationUrgency.Critical ? "priority_high" : "";
    }

    function getNotifIcon(summary: string, urgency: int): string {
        const fallback = urgency === NotificationUrgency.Critical ? "release_alert" : "chat";
        return matchIcon(summary.toLowerCase(), notifIconRules, fallback);
    }

    function getVolumeIcon(volume: real, isMuted: bool): string {
        if (isMuted)
            return "no_sound";
        if (volume >= 0.5)
            return "volume_up";
        if (volume > 0)
            return "volume_down";
        return "volume_mute";
    }

    function getMicVolumeIcon(volume: real, isMuted: bool): string {
        return !isMuted && volume > 0 ? "mic" : "mic_off";
    }

    function getTrayIcon(id: string, icon: string): string {
        for (const sub of GlobalConfig.bar.tray.iconSubs.values)
            if (sub.id === id)
                return sub.image ? Qt.resolvedUrl(sub.image) : Quickshell.iconPath(sub.icon);

        if (icon.includes("?path=")) {
            const [name, path] = icon.split("?path=");
            const file = name.slice(name.lastIndexOf("/") + 1);
            const themed = Quickshell.iconPath(file, true);
            icon = themed ? themed : Qt.resolvedUrl(`${path}/${file}`);
        }
        return icon;
    }

    function getBatteryIcon(percentage: real, charging = false): string {
        if (percentage === 1)
            return charging ? "battery_charging_full" : "battery_full";
        let level = Math.floor(percentage * 7);
        if (charging && (level === 4 || level === 1))
            level--;
        return charging ? `battery_charging_${(level + 3) * 10}` : `battery_${level}_bar`;
    }
}
