.pragma library

// Uptime in two short lines for narrow places (the session panel): "12 h" / "41 min", or "3 d" / "2 h".
function compact(seconds) {
    var s = Math.max(0, Math.floor(seconds || 0));
    var days = Math.floor(s / 86400), hours = Math.floor((s % 86400) / 3600), minutes = Math.floor((s % 3600) / 60);
    return days > 0 ? [days + " d", hours + " h"] : [hours + " h", minutes + " min"];
}
