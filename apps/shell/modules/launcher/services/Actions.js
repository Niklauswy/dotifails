.pragma library

// Secondary actions shown in the Ctrl+K popover. `id` is dispatched by the panel;
// `shortcut` is only a label except for "Ctrl ↵" (second action) and "Ctrl Del" (delete).

function a(id, title, icon, shortcut, danger) {
    return {id, title, icon, shortcut: shortcut || "", danger: !!danger};
}

function primaryLabel(row) {
    if (!row)
        return "Open";
    switch (row.kind) {
    case "calc": case "clip": case "snippet": case "history": return "Copy";
    case "window": return "Switch";
    case "run": case "openwith": return row.kind === "run" ? "Run" : "Open";
    case "cmd": return row.view || row.form ? "Open" : "Run";
    case "web": return "Search";
    }
    return "Open";
}

function actionsFor(row, pinned, desktopActions) {
    if (!row)
        return [];
    const pin = a("pin", pinned ? "Unpin from Favorites" : "Pin to Favorites", pinned ? "keep_off" : "keep");
    switch (row.kind) {
    case "app":
        return [a("open", "Open", "open_in_new", "↵")].concat(
            (desktopActions || []).map((d, i) => a("desktop:" + i, d.name, "chevron_right")),
            [a("copy-title", "Copy Name", "content_copy"), pin]);
    case "cmd":
        return [a("open", row.view || row.form ? "Open" : "Run", "play_arrow", "↵"), pin];
    case "file":
        return [
            a("open", "Open", "open_in_new", "↵"),
            a("folder", "Show in Folder", "folder_open", "Ctrl ↵"),
            a("openwith", "Open With…", "apps"),
            a("copy-path", "Copy Path", "content_copy"),
            a("copy-title", "Copy Name", "badge"),
            a("copy-file", "Copy File", "file_copy"),
            pin];
    case "clip": {
        const list = [a("copy", "Copy to Clipboard", "content_copy", "↵"), a("paste", "Paste to Previous Window", "content_paste_go", "Ctrl ↵")];
        if (row.clip_kind === "image")
            list.push(a("open-image", "Open Image", "image"));
        list.push(a("delete", "Delete Entry", "delete", "Ctrl Del", true), a("capture", "Pause or Resume Capture", "pause_circle"), a("clear", "Clear History", "delete_sweep", "", true));
        return list;
    }
    case "snippet":
        return [a("copy", "Copy to Clipboard", "content_copy", "↵"), a("paste", "Paste to Previous Window", "content_paste_go", "Ctrl ↵"), a("edit", "Edit Snippet", "edit"), a("delete", "Delete Snippet", "delete", "Ctrl Del", true)];
    case "calc":
        return [a("copy", "Copy Result", "content_copy", "↵"), a("paste", "Paste to Previous Window", "content_paste_go", "Ctrl ↵"), a("copy-expression", "Copy Expression", "function")];
    case "history":
        return [a("copy", "Copy Result", "content_copy", "↵"), a("paste", "Paste to Previous Window", "content_paste_go", "Ctrl ↵")];
    case "window":
        return [a("open", "Switch to Window", "web_asset", "↵"), a("close-window", "Close Window", "close", "", true)];
    case "web":
        return [a("open", "Search the Web", "travel_explore", "↵")];
    case "run":
        return [a("open", "Run in Terminal", "terminal", "↵")];
    case "openwith":
        return [a("open", "Open File With This App", "open_in_new", "↵")];
    }
    return [a("open", "Open", "open_in_new", "↵")];
}
