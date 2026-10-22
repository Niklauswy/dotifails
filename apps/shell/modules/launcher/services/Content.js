.pragma library

// Presentation only: preserve the original clipboard value and storage type.
function textKind(value) {
    const text = String(value || "").trim();
    if (/^https?:\/\/[^\s]+$/i.test(text)) return "link";
    if (/^[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)(?:e[+-]?\d+)?$/i.test(text)) return "number";
    // QML's Array.from(string) can split UTF-16 surrogate pairs; walk code points explicitly.
    const points = [];
    for (let i = 0; i < text.length;) {
        const n = text.codePointAt(i);
        points.push(text.slice(i, i + (n > 0xffff ? 2 : 1)));
        i += n > 0xffff ? 2 : 1;
    }
    let emoji = false;
    if (points.length && points.length <= 64 && points.every(c => {
        const n = c.codePointAt(0);
        if ((n >= 0x1f000 && n <= 0x1faff) || (n >= 0x2600 && n <= 0x27bf)
                || [0x00a9, 0x00ae, 0x203c, 0x2049, 0x2122, 0x2139, 0x3030, 0x303d, 0x3297, 0x3299, 0x20e3].includes(n)) {
            emoji = true;
            return true;
        }
        return /\s/.test(c) || n === 0xfe0f || n === 0x200d || (n >= 0xe0020 && n <= 0xe007f)
            || (text.includes("\u20e3") && /[0-9#*]/.test(c));
    }) && emoji) return "emoji";
    return "text";
}
