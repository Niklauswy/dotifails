.pragma library

function tokens(value) {
    const n = Number(value) || 0;
    const units = [[1e9, "B"], [1e6, "M"], [1e3, "K"]];
    for (const [size, unit] of units) {
        if (n >= size) {
            const scaled = n / size;
            return (scaled >= 100 ? scaled.toFixed(0) : scaled >= 10 ? scaled.toFixed(1) : scaled.toFixed(2)).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "") + unit;
        }
    }
    return String(Math.round(n));
}

function money(value) {
    const n = Number(value) || 0;
    if (n > 0 && n < 0.01)
        return "<$0.01";
    return "$" + n.toLocaleString(Qt.locale("en_US"), "f", 2);
}

function percent(fraction) {
    const p = (Number(fraction) || 0) * 100;
    if (p > 0 && p < 0.1)
        return "<0.1%";
    return p.toFixed(1) + "%";
}

// Compact countdown, e.g. "3d 20h", "1h 45m", "12m".
function countdown(epochSeconds, nowMs) {
    if (!epochSeconds)
        return "";
    const total = Math.max(0, Math.round(epochSeconds - nowMs / 1000));
    const days = Math.floor(total / 86400);
    const hours = Math.floor(total % 86400 / 3600);
    const minutes = Math.floor(total % 3600 / 60);
    if (days > 0)
        return days + "d " + hours + "h";
    if (hours > 0)
        return hours + "h " + minutes + "m";
    return Math.max(1, minutes) + "m";
}

// Elapsed time since a snapshot, e.g. "now", "5m", "2h".
function age(epochSeconds, nowMs) {
    if (!epochSeconds)
        return "";
    const seconds = Math.max(0, nowMs / 1000 - epochSeconds);
    if (seconds < 60)
        return "";
    if (seconds < 3600)
        return Math.floor(seconds / 60) + "m";
    if (seconds < 86400)
        return Math.floor(seconds / 3600) + "h";
    return Math.floor(seconds / 86400) + "d";
}

// How usage compares with an even spend over the window.
// delta > 0 means ahead of pace (spending faster than the window allows).
function pace(limit, nowMs) {
    if (!limit || !limit.resetsAt || !limit.windowMinutes)
        return null;
    const windowSeconds = limit.windowMinutes * 60;
    const left = limit.resetsAt - nowMs / 1000;
    const elapsed = Math.max(0, Math.min(1, 1 - left / windowSeconds));
    if (elapsed < 0.02)
        return null;
    const delta = limit.usedPercent - elapsed * 100;
    const rate = limit.usedPercent / (elapsed * windowSeconds);
    const runsOutIn = rate > 0 ? (100 - limit.usedPercent) / rate : Infinity;
    return { delta: delta, lasts: runsOutIn >= left, runsOutAt: nowMs / 1000 + runsOutIn };
}
