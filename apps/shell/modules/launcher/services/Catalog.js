.pragma library

function categories() {
    return [
        {id: "all", title: "Discover", icon: "explore"},
        {id: "apps", title: "Applications", icon: "apps"},
        {id: "files", title: "Files", icon: "folder_open"},
        {id: "clip", title: "Clipboard", icon: "content_paste"},
        {id: "snippets", title: "Snippets", icon: "data_object"},
        {id: "calc", title: "Calculator", icon: "calculate"},
        {id: "windows", title: "Windows", icon: "view_carousel"},
        {id: "commands", title: "Commands", icon: "terminal"}
    ];
}

function actions(query, configured, enableDangerous) {
    const defaults = [
        ["Clipboard", "Search copied text, images, colours and links", "content_paste", ["autocomplete", "clip"]],
        ["Snippets", "Saved phrases and abbreviations", "data_object", ["autocomplete", "snippets"]],
        ["Calculator", "Arithmetic, percentages, conversions and history", "calculate", ["autocomplete", "calc"]],
        ["Windows", "Find and switch to an open window", "view_carousel", ["autocomplete", "windows"]],
        ["Wysun Music Mini", "Compact playback controls", "album", ["wysun", "music-mini"]],
        ["Wysun Tools", "Projects, diagnostics and local files", "terminal", ["wysun", "tools"]],
        ["Calendar", "Dates and your desktop overview", "calendar_month", ["wysun", "calendar"]],
        ["System", "Memory, load and battery", "monitoring", ["wysun", "system"]],
        ["Wallpaper & style", "Personalise your Wysun desktop", "wallpaper", ["wysun", "settings", "wallpaper"]],
        ["Wysun Settings", "Display, appearance and desktop preferences", "settings", ["wysun", "settings"]],
        ["Wysun Files", "Browse folders and preview documents", "folder", ["wysun", "files"]],
        ["Wysun Music", "Your music library and playback", "music_note", ["wysun", "music"]],
        ["Wysun Notes", "Write and find your local notes", "notes", ["wysun", "notes"]],
        ["Wysun Colors", "Pick, convert and save colours", "colorize", ["wysun", "colors"]],
        ["Wysun Recorder", "Record your screen or open the library", "videocam", ["wysun", "recorder"]],
        ["Wysun Screenshot", "Capture your screen or open the library", "screenshot", ["wysun", "screenshot"]],
        ["Connections", "Wi-Fi, Bluetooth, VPN and SSH", "wifi", ["wysun", "connections"]],
        ["Processes", "Inspect running apps and resource usage", "memory", ["wysun", "processes"]],
        ["Sound", "Volume and audio devices", "volume_up", ["wysun", "audio"]],
        ["Notifications", "History and focus mode", "notifications", ["wysun", "notifications"]],
        ["Emoji", "Open the emoji drop-down · Super+Ctrl+Period", "emoji_emotions", ["wysun", "emoji"]],
        ["Session & power", "Lock, suspend, sign out or shut down", "power_settings_new", ["wysun", "power"]],
        ["Lock screen", "Lock your Wysun session", "lock", ["wysun", "lock"]],
        ["Terminal", "Open your configured terminal", "terminal", ["wysun-terminal"]]
    ];
    const user = (configured || []).map(a => ({name: a.name, description: a.description, icon: a.icon, command: Array.from(a.command || []), enabled: a.enabled, dangerous: a.dangerous}));
    const keys = user.map(a => JSON.stringify(a.command));
    const entries = user.concat(defaults.filter(e => !keys.includes(JSON.stringify(e[3]))).map(e => ({name: e[0], description: e[1], icon: e[2], command: e[3], enabled: true})))
        .filter(a => a.enabled !== false && (!a.dangerous || enableDangerous) && JSON.stringify(a.command) !== '["wysun","wallpaper","-r"]')
        .map(a => [a.name || "Custom action", a.description || "Desktop action", a.icon || "bolt", a.command]);
    const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    return entries.filter(e => words.every(w => (e[0] + " " + e[1]).toLowerCase().includes(w)))
        .map(e => ({kind: "action", title: e[0], subtitle: e[1], icon: e[2], argv: e[3], section: "Desktop actions"}));
}
