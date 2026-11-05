.pragma library

// Pure helpers of the Wysun Drive bar icon and popout (services/Drive.qml); tested with node
// (tests/shell_bridge/test_drive_logic.py). An upload is the JSON of
// $XDG_RUNTIME_DIR/wysun-drive/<pid>.json (apps/python/wysun_drive/status.py).

var STALE = 30;   // seconds without a heartbeat (the uploader writes every 10 s) = gone

function live(list, nowSec) {
    return (list || []).filter(function (u) {
        return u && typeof u.pid === "number" && typeof u.updated === "number" && nowSec - u.updated <= STALE;
    }).sort(function (a, b) {
        return (a.started || 0) - (b.started || 0);
    });
}

function fraction(upload) {
    if (!upload || !upload.total)
        return 0;
    return Math.max(0, Math.min(1, upload.done / upload.total));
}

function size(bytes) {
    var units = ["B", "KB", "MB", "GB", "TB"];
    var n = Math.max(0, bytes || 0), i = 0;
    while (n >= 1024 && i < units.length - 1) {
        n /= 1024;
        i++;
    }
    return (i === 0 ? String(Math.round(n)) : n.toFixed(1).replace(".", ",")) + " " + units[i];
}

function detail(upload) {
    if (!upload || !upload.total)
        return "Preparando…";
    return size(upload.done) + " de " + size(upload.total) + " · " + Math.round(fraction(upload) * 100) + " %";
}

function overall(uploads) {
    var done = 0, total = 0;
    (uploads || []).forEach(function (u) {
        done += u.done || 0;
        total += u.total || 0;
    });
    return total ? Math.max(0, Math.min(1, done / total)) : 0;
}
