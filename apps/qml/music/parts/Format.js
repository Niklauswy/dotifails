// Music's small formatting helpers for QML (the Python side has the same rules in quick/text.py).
.pragma library

function clock(seconds) {
    const s = Math.max(0, Math.floor(seconds || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const pad = n => (n < 10 ? "0" : "") + n;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(s % 60) : m + ":" + pad(s % 60);
}
