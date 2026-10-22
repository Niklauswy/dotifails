.pragma library

// Commands the launcher can run. `view` pushes a launcher view, `emoji` opens the emoji drawer,
// `argv` is executed detached. Rows are plain data so they can be filtered in JS per keystroke.

function make(id, title, subtitle, icon, extra, aux) {
    return Object.assign({kind: "cmd", key: "cmd:" + id, id, title, subtitle, icon, type: "Command", l: title.toLowerCase(), a: ((aux || "") + " " + subtitle).toLowerCase()}, extra);
}

function views() {
    return [
        make("clipboard", "Clipboard History", "Text, images, colours and links you copied", "content_paste", {view: "clipboard"}, "paste copy history"),
        make("files", "Search Files", "Find files and folders in your home", "folder_open", {view: "files"}, "documents find"),
        make("apps", "All Applications", "Everything installed", "apps", {view: "apps"}, "launch programs"),
        make("calc-history", "Calculator History", "Results you copied from the calculator", "calculate", {view: "calc-history"}, "math"),
        make("emoji", "Emoji", "Open the emoji picker", "emoji_emotions", {emoji: true}, "smiley symbols")
    ];
}

function tools(configured) {
    const w = (id, title, subtitle, icon, argv, aux) => make(id, title, subtitle, icon, {argv}, aux);
    const builtin = [
        w("wallpaper", "Wallpaper & Style", "Personalise your Wysun desktop", "wallpaper", ["wysun", "settings", "wallpaper"], "theme background"),
        w("settings", "Wysun Settings", "Displays, workspaces and desktop preferences", "settings", ["wysun", "settings"], "preferences"),
        w("files-app", "Wysun Files", "Browse folders and preview documents", "folder", ["wysun", "files"], "file manager"),
        w("music", "Wysun Music", "Your music library and playback", "music_note", ["wysun", "music"], "player"),
        w("music-mini", "Wysun Music · widget", "Playback controls in the media widget", "album", ["wysun", "music-mini"], "player"),
        w("colors", "Wysun Colors", "Pick, convert and save colours", "colorize", ["wysun", "colors"], "picker"),
        w("recorder", "Wysun Recorder", "Record your screen or open the library", "videocam", ["wysun", "recorder"], "screen record"),
        // Waits for the launcher to close so it is not in the frozen frame.
        w("screenshot", "Screenshot", "Copy, annotate or read the text of a region", "screenshot", ["sh", "-c", "sleep 0.25; exec wysun-shell screenshot"], "capture ocr annotate"),
        w("processes", "Processes", "Inspect running apps and resource usage", "memory", ["wysun", "processes"], "task manager cpu"),
        w("sound", "Sound", "Volume and audio devices", "volume_up", ["wysun", "audio"], "audio"),
        w("notifications", "Notifications", "History and focus mode", "notifications", ["wysun", "notifications"], "do not disturb"),
        w("calendar", "Calendar", "Dates and your desktop overview", "calendar_month", ["wysun", "calendar"], ""),
        w("terminal", "Terminal", "Open your configured terminal", "terminal", ["wysun-terminal"], "shell console")
    ];
    const known = {};
    for (const c of builtin)
        if (c.argv) known[JSON.stringify(c.argv)] = true;
    const custom = [];
    for (const a of configured) {
        const cmd = Array.from(a.command || []);
        if (a.enabled === false || !a.name || !cmd.length || cmd[0] === "autocomplete" || known[JSON.stringify(cmd)])
            continue;
        if (cmd.join(" ") === "wysun wallpaper -r")
            continue;
        custom.push(make("custom:" + a.name, a.name, a.description || "Custom action", a.icon || "bolt", {argv: cmd, confirm: !!a.dangerous}, ""));
    }
    return builtin.concat(custom);
}
