.pragma library

// Secondary actions shown in the Alt+K popover. `id` is dispatched by the panel;
// `shortcut` is only a label except for "Alt ↵" (second action) and "Alt Del" (delete).

function a(id, title, icon, shortcut, danger) {
    return {id, title, icon, shortcut: shortcut || "", danger: !!danger};
}

function primaryLabel(row) {
    if (!row)
        return "Open";
    switch (row.kind) {
    case "calc": case "clip": case "history": case "translate": case "variant": case "value": return "Copy";
    case "link": return "Open";
    case "timer": return "Start";
    case "kill": return "Quit";
    case "run": case "openwith": return row.kind === "run" ? "Run" : "Open";
    case "cmd": return row.view ? "Open" : "Run";
    case "web": return "Search";
    case "file": return row.isDir ? "Browse" : row.editable ? "Edit" : "Open";
    }
    return "Open";
}

function actionsFor(row, pinned, desktopActions) {
    return grouped(rawActions(row, pinned, desktopActions));
}

// Group 0: the primary action, 1: the rest, 2: destructive ones.
function grouped(list) {
    return list.map((x, i) => Object.assign(x, {group: x.danger ? 2 : (i === 0 ? 0 : 1)}));
}

function rawActions(row, pinned, desktopActions) {
    if (!row)
        return [];
    const pin = a("pin", pinned ? "Unpin from Favorites" : "Pin to Favorites", pinned ? "keep_off" : "keep");
    switch (row.kind) {
    case "app":
        return [a("open", "Open", "open_in_new", "↵")].concat(
            (desktopActions || []).map((d, i) => a("desktop:" + i, d.name, "chevron_right")),
            [a("copy-title", "Copy Name", "content_copy"), pin]);
    case "cmd":
        return [a("open", row.view ? "Open" : "Run", "play_arrow", "↵"), pin];
    case "file":
        if (row.isDir)
            return [
                a("open", "Browse Folder", "subdirectory_arrow_right", "↵"),
                a("open-app", "Open in File Manager", "folder_open"),
                a("folder", "Show in Folder", "drive_file_move", "Alt ↵"),
                a("copy-path", "Copy Path", "content_copy"),
                a("copy-title", "Copy Name", "badge"),
                pin];
        return [
            a("open", row.editable ? "Edit in Neovim" : "Open", row.editable ? "edit_note" : "open_in_new", "↵"),
            a("folder", "Show in Folder", "folder_open", "Alt ↵")].concat(row.editable ? [a("xdg", "Open with Default App", "open_in_new")] : [], [
            a("openwith", "Open With…", "apps"),
            a("copy-path", "Copy Path", "content_copy"),
            a("copy-title", "Copy Name", "badge"),
            a("copy-file", "Copy File", "file_copy"),
            pin]);
    case "clip": {
        const list = [a("copy", "Copy to Clipboard", "content_copy", "↵"), a("paste", "Paste to Previous Window", "content_paste_go", "Alt ↵")];
        if (/^https?:\/\/[^\s]+$/i.test(row.value || ""))
            list.push(a("open-link", "Open Web Page", "open_in_new"));
        if (row.clip_kind === "image")
            list.splice(2, 0, a("copy-text", "Copy Text from Image", "text_fields"), a("open-image", "Open Image", "image"));
        list.push(a("delete", "Delete Entry", "delete", "Alt Del", true), a("capture", "Pause or Resume Capture", "pause_circle"), a("clear", "Clear History", "delete_sweep", "", true));
        return list;
    }
    case "calc":
        return [a("copy", "Copy Result", "content_copy", "↵"), a("paste", "Paste to Previous Window", "content_paste_go", "Alt ↵"), a("copy-expression", "Copy Expression", "function")];
    case "history":
        return [a("copy", "Copy Result", "content_copy", "↵"), a("paste", "Paste to Previous Window", "content_paste_go", "Alt ↵")];
    case "web":
        return [a("open", row.site ? "Search " + row.site : "Search the Web", "travel_explore", "↵")];
    case "variant":
    case "value":
        return [a("copy-variant", "Copy", "content_copy", "↵")];
    case "link":
        return [a("open", "Open in Browser", "open_in_new", "↵"), a("copy-link", "Copy Link", "link")];
    case "timer":
        return [a("open", "Start Timer", "timer", "↵")];
    case "kill":
        return [a("open", "Quit All of Them", "dangerous", "↵")];
    case "translate":
        return [a("copy-translation", "Copy Translation", "content_copy", "↵"), a("open-translate", "Open in Google Translate", "open_in_new", "Alt ↵"), a("copy-original", "Copy Original Text", "format_quote")];
    case "run":
        return [a("open", "Run in Terminal", "terminal", "↵")];
    case "openwith":
        return [a("open", "Open File With This App", "open_in_new", "↵")];
    }
    return [a("open", "Open", "open_in_new", "↵")];
}
