.pragma library

// Which windows study mode lets through, which it hides and where they go back. Pure functions.

var HIDDEN_WORKSPACE = "special:wysun-study";
// The shell's own apps, portals, the screen-share picker and polkit agents are never hidden.
var NEVER_BLOCK = [/^wysun/i, /^xdg-desktop-portal/i, /^hyprland-share-picker$/i, /polkit/i];

function isAllowed(windowClass, allowedClasses) {
    if (!windowClass)
        return true;
    for (var i = 0; i < NEVER_BLOCK.length; i++)
        if (NEVER_BLOCK[i].test(windowClass))
            return true;
    var lower = windowClass.toLowerCase();
    for (var j = 0; j < allowedClasses.length; j++)
        if (String(allowedClasses[j]).toLowerCase() === lower)
            return true;
    return false;
}

// windows: [{address, class, workspace}]. Windows the user keeps in a special workspace are left alone.
function toHide(windows, allowedClasses) {
    var out = [];
    for (var i = 0; i < windows.length; i++) {
        var w = windows[i];
        if (String(w.workspace).indexOf("special:") === 0 || isAllowed(w["class"], allowedClasses))
            continue;
        out.push({address: w.address, workspace: w.workspace});
    }
    return out;
}

// Hyprland drops empty workspaces, so a numbered one is recreated by moving a window back to it; a named one
// that no longer exists falls back to the monitor's active workspace.
function restoreTarget(origWorkspace, existingWorkspaceNames, activeOnMonitor) {
    var name = String(origWorkspace);
    return /^-?\d+$/.test(name) || existingWorkspaceNames.indexOf(name) >= 0 ? name : String(activeOnMonitor);
}

// Hidden workspace stays out of the shell's special-workspace lists.
function isHiddenWorkspace(name) {
    return name === HIDDEN_WORKSPACE;
}
