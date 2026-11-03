.pragma library

// Pure helpers of the window tools that Wysun Processes asks the shell for (services/WindowTools.qml): window
// thumbnails and locate-on-screen. Tested with node (tests/shell_bridge/test_window_tools.py).

var MAX_THUMBS = 24;
// Capture width in device pixels: the default keeps every existing caller sharp enough for a row thumbnail, while
// Processes asks for the sheet's real size. Clamped so neither the CLI nor a buggy caller can request an absurd image.
var DEFAULT_THUMB_WIDTH = 480;
var MIN_THUMB_WIDTH = 160;
var MAX_THUMB_WIDTH = 1920;

// "0xaa,0xBB,…" -> ["aa", "bb"]: valid hex addresses only, lower case, without 0x, no repeats, at most 24.
function parseAddresses(text) {
    var out = [];
    String(text || "").split(",").forEach(function (part) {
        var m = /^\s*(?:0x)?([0-9a-fA-F]+)\s*$/.exec(part);
        if (m && out.indexOf(m[1].toLowerCase()) < 0 && out.length < MAX_THUMBS)
            out.push(m[1].toLowerCase());
    });
    return out;
}

// One address for actions that target a single window (locate); "" for anything else, so malformed or
// repeated input never reaches a dispatch.
function singleAddress(text) {
    var out = parseAddresses(text);
    return out.length === 1 ? out[0] : "";
}

function sameAddress(a, b) {
    var strip = function (v) { return String(v || "").toLowerCase().replace(/^0x/, ""); };
    return strip(a) !== "" && strip(a) === strip(b);
}

// Where the halo goes on `screen` ({name, activeWs}) for a window ({at, size}) on `monitor`
// ({name, x, y, width, height}) and workspace `ws`: hidden unless that screen shows that workspace.
function placement(win, monitor, screen, ws) {
    if (!win || !monitor || !screen || monitor.name !== screen.name || screen.activeWs !== ws)
        return {visible: false, x: 0, y: 0, width: 0, height: 0};
    return {visible: true, x: win.at[0] - monitor.x, y: win.at[1] - monitor.y, width: win.size[0], height: win.size[1]};
}

// `workspace` is the window's workspace id and `monitor` its monitor ({activeWorkspace}): true when locating has to
// focus the window first (it is on another workspace, or its monitor is not showing it) before drawing the halo.
function needsFocus(workspace, monitor) {
    return !monitor || monitor.activeWorkspace !== workspace;
}

// Optional capture width from the CLI or IPC: digits only (anything else is the default) and clamped to 160–1920.
function thumbWidth(value) {
    var digits = /^\s*(\d+)\s*$/.exec(String(value ?? ""));
    if (!digits)
        return DEFAULT_THUMB_WIDTH;
    return Math.min(MAX_THUMB_WIDTH, Math.max(MIN_THUMB_WIDTH, parseInt(digits[1], 10)));
}

function cleanAddress(address) {
    var clean = String(address ?? "").toLowerCase().replace(/^0x/, "");
    return /^[0-9a-f]+$/.test(clean) ? clean : "";
}

// One entry per (address, width): a large capture for the sheet never replaces the small one of the row, nor the
// other way around.
function thumbKey(address, width) {
    return cleanAddress(address) + "@" + thumbWidth(width);
}

// Only ever inside `runtimeDir` (see the header of services/WindowTools.qml): addresses are hex, widths are numbers.
// The optional `generation` makes each capture its own file: a capture is never written over the file the app is
// already showing (a reader would see a truncated PNG while the compositor keeps the old one).
function thumbPath(runtimeDir, address, width, generation) {
    var clean = cleanAddress(address);
    if (!clean)
        return "";
    var gen = Number(generation);
    var stamp = Number.isInteger(gen) && gen > 0 ? "-" + gen : "";
    return runtimeDir + "/wysun-processes/thumbs/" + clean + "@" + thumbWidth(width) + stamp + ".png";
}

// The size of a capture: the requested width and the window's own aspect (16:9 while Hyprland has no size yet).
function thumbSize(size, width) {
    var w = thumbWidth(width);
    var has = size && size.length >= 2 && size[0] > 0 && size[1] > 0;
    return {width: w, height: has ? Math.max(1, Math.round(w * size[1] / size[0])) : Math.round(w * 9 / 16)};
}
