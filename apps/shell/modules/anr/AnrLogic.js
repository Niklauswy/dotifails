.pragma library

// Pure helpers of the Wysun card for unresponsive windows (Anr.qml). Hyprland keeps its own ANR dialog
// (hyprland-dialog, misc:enable_anr_dialog untouched); the shell recognises it, reads which window hung from the
// dialog's command line and shows its own card. Tested with node (tests/shell_bridge/test_anr_logic.py).

var TITLE = "Application Not Responding";
var PROTECTED = ["quickshell", "hyprland", "xwayland", "wysun-shell"];

function isAnrDialog(cls, title) {
    return String(title || "") === TITLE;
}

// "/proc/<pid>/cmdline" text (NUL separated) -> {title, cls} of the hung window, or null.
function parseCmdline(text) {
    var args = String(text || "").split("\u0000");
    var i = args.indexOf("--text");
    if (i < 0 || i + 1 >= args.length)
        return null;
    var m = /^An application (.*) - ([^ ]*) is not responding\.$/.exec(args[i + 1]);
    return m ? {title: m[1], cls: m[2]} : null;
}

// The window that hung among `windows` ([{address, cls, title, pid}]); the only window of that class if titles
// changed meanwhile. Never a piece of the session.
function matchWindow(windows, wanted) {
    if (!wanted || PROTECTED.indexOf(String(wanted.cls).toLowerCase()) >= 0)
        return null;
    var list = (windows || []).filter(function (w) { return w.cls === wanted.cls; });
    var exact = list.filter(function (w) { return w.title === wanted.title; });
    var found = exact.length ? exact[0] : list.length === 1 ? list[0] : null;
    return found ? {address: found.address, cls: found.cls, title: found.title, pid: found.pid} : null;
}
