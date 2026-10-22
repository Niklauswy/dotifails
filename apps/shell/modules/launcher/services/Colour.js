.pragma library

// Clipboard colours arrive as written: #hex, rgb(...) or hsl(...). Qt only parses the first,
// so the other two are converted here (alpha is ignored, like the Colours panel does).
function parse(text) {
    const value = String(text || "").trim();
    let m = value.match(/^rgba?\(\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)/i);
    if (m)
        return Qt.rgba(Math.min(255, m[1]) / 255, Math.min(255, m[2]) / 255, Math.min(255, m[3]) / 255, 1);
    m = value.match(/^hsla?\(\s*(\d+(?:\.\d+)?)(?:deg)?\s*[, ]\s*(\d+(?:\.\d+)?)%\s*[, ]\s*(\d+(?:\.\d+)?)%/i);
    if (m)
        return Qt.hsla((m[1] % 360) / 360, Math.min(100, m[2]) / 100, Math.min(100, m[3]) / 100, 1);
    return Qt.color(value);
}
