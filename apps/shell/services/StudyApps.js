.pragma library

// Which windows study mode hides and where they go back. Only the apps the user lists are blocked
// (Brave by default); everything else keeps working. Pure functions.

var HIDDEN_WORKSPACE = "special:wysun-study";
// The shell's own apps, portals, the screen-share picker and polkit agents are never hidden.
var NEVER_BLOCK = [/^wysun/i, /^xdg-desktop-portal/i, /^hyprland-share-picker$/i, /polkit/i];

function isBlocked(windowClass, blockedClasses) {
    if (!windowClass)
        return false;
    for (var i = 0; i < NEVER_BLOCK.length; i++)
        if (NEVER_BLOCK[i].test(windowClass))
            return false;
    var lower = windowClass.toLowerCase();
    for (var j = 0; j < blockedClasses.length; j++)
        if (String(blockedClasses[j]).toLowerCase() === lower)
            return true;
    return false;
}

// windows: [{address, class, workspace}]. Windows the user keeps in a special workspace are left alone.
function toHide(windows, blockedClasses) {
    var out = [];
    for (var i = 0; i < windows.length; i++) {
        var w = windows[i];
        if (String(w.workspace).indexOf("special:") === 0 || !isBlocked(w["class"], blockedClasses))
            continue;
        out.push({address: w.address, workspace: w.workspace});
    }
    return out;
}

// Hyprland drops empty workspaces but recreates one when a window moves to it (by id, or by "name:"), so a
// window always goes back to its own; only one with no record falls back to the monitor's active workspace.
function restoreTarget(origWorkspace, existingWorkspaceNames, activeOnMonitor) {
    var name = origWorkspace === undefined || origWorkspace === null ? "" : String(origWorkspace);
    return name && name.indexOf("special:") !== 0 ? name : String(activeOnMonitor);
}

// Dispatch target for a workspace: numbers are ids, special:… is already a selector, anything else is a
// name and needs "name:" (a bare "mail" would read as a monitor selector, "-1" as the previous workspace).
function workspaceSelector(name) {
    var s = String(name);
    if (/^\d+$/.test(s) || s.indexOf("special:") === 0)
        return s;
    return "name:" + s;
}

// Hidden workspace stays out of the shell's special-workspace lists.
function isHiddenWorkspace(name) {
    return name === HIDDEN_WORKSPACE;
}
