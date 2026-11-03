// Number formats of Wysun Processes (Spanish, decimal comma kept as a point to match the shell).
.pragma library

function pct(v) {
    if (v === undefined || v === null || v < 0)
        return "—";
    return v < 0.05 ? "0 %" : v < 10 ? v.toFixed(1) + " %" : Math.round(v) + " %";
}

function mem(bytes) {
    const mb = (bytes || 0) / 1048576;
    return mb >= 1024 ? (mb / 1024).toFixed(1) + " GB" : Math.round(mb) + " MB";
}

function rate(bps) {
    const v = bps || 0;
    if (v < 1024)
        return v < 1 ? "0" : Math.round(v) + " B/s";
    if (v < 1048576)
        return Math.round(v / 1024) + " KB/s";
    return (v / 1048576).toFixed(1) + " MB/s";
}

function age(seconds) {
    const s = Math.max(0, seconds || 0);
    if (s >= 86400)
        return Math.floor(s / 86400) + " d " + Math.floor(s % 86400 / 3600) + " h";
    if (s >= 3600)
        return Math.floor(s / 3600) + " h " + Math.floor(s % 3600 / 60) + " min";
    if (s >= 60)
        return Math.floor(s / 60) + " min";
    return Math.floor(s) + " s";
}

function stateColourRole(state) {
    return ({ R: "success", T: "tertiary", t: "tertiary", D: "primary", Z: "error" })[state] || "outline";
}

// Indices of up to `count` peaks of `series` (local maxima well above the mean), highest first.
function peaks(series, count) {
    const n = series ? series.length : 0;
    if (n < 5)
        return [];
    let sum = 0;
    for (let i = 0; i < n; i++)
        sum += series[i];
    const mean = sum / n;
    let sq = 0;
    for (let i = 0; i < n; i++)
        sq += (series[i] - mean) * (series[i] - mean);
    const sd = Math.sqrt(sq / n);
    const out = [];
    for (let i = 2; i < n - 2; i++) {
        const v = series[i];
        if (v > mean + 1.3 * sd && v > 0.5 && v >= series[i - 1] && v >= series[i + 1] && v >= series[i - 2] && v >= series[i + 2])
            out.push(i);
    }
    out.sort((a, b) => series[b] - series[a]);
    return out.slice(0, count);
}
