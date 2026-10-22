.pragma library

// Inline calculator: arithmetic, percentages, functions and unit conversions.
// Pure JS over a recursive-descent parser; nothing is evaluated with eval().

const UNITS = {
    km: ["length", 1000], m: ["length", 1], cm: ["length", 0.01], mm: ["length", 0.001],
    mi: ["length", 1609.344], ft: ["length", 0.3048], in: ["length", 0.0254], yd: ["length", 0.9144],
    kg: ["mass", 1000], g: ["mass", 1], lb: ["mass", 453.59237], oz: ["mass", 28.349523125],
    s: ["time", 1], min: ["time", 60], h: ["time", 3600], d: ["time", 86400],
    gb: ["data", 1e9], mb: ["data", 1e6], kb: ["data", 1e3], tb: ["data", 1e12],
    l: ["volume", 1], ml: ["volume", 0.001], gal: ["volume", 3.785411784]
};
const FUNCS = {
    sqrt: Math.sqrt, abs: Math.abs, sin: Math.sin, cos: Math.cos, tan: Math.tan, ln: Math.log,
    log: Math.log10, round: Math.round, floor: Math.floor, ceil: Math.ceil, exp: Math.exp
};

function format(n) {
    if (!isFinite(n) || Math.abs(n) > 1e100)
        return null;
    return String(Number(n.toPrecision(12)));
}

function tokenize(q) {
    const out = [];
    const re = /\s*(\d+(?:\.\d+)?|\.\d+|[a-z]+|\*\*|[-+*\/%^()])/gy;
    let m, last = 0;
    while ((m = re.exec(q)) !== null) {
        out.push(m[1]);
        last = re.lastIndex;
    }
    return q.slice(last).trim() === "" ? out : null;
}

function parse(tokens) {
    let i = 0;
    let operators = 0;
    const peek = () => tokens[i];
    const take = () => tokens[i++];
    function primary() {
        const t = take();
        if (t === undefined)
            throw 0;
        if (t === "(") {
            const v = sum();
            if (take() !== ")")
                throw 0;
            return v;
        }
        if (t === "-")
            return -power();
        if (t === "+")
            return power();
        if (/^[\d.]/.test(t)) {
            let v = parseFloat(t);
            const next = tokens[i + 1];
            const operand = next !== undefined && (/^[\d.a-z(]/.test(next) || next === "-");
            if (peek() === "%" && !operand) {
                take();
                operators++;
                v /= 100;
            }
            return v;
        }
        if (t === "pi")
            return Math.PI;
        if (t === "e")
            return Math.E;
        if (FUNCS[t] && peek() === "(") {
            operators++;
            take();
            const v = sum();
            if (take() !== ")")
                throw 0;
            return FUNCS[t](v);
        }
        throw 0;
    }
    function power() {
        const base = primary();
        if (peek() === "^" || peek() === "**") {
            take();
            operators++;
            const e = power();
            if (Math.abs(e) > 1000 || Math.abs(base) > 1e50)
                throw 0;
            return Math.pow(base, e);
        }
        return base;
    }
    function product() {
        let v = power();
        while (peek() === "*" || peek() === "/" || (peek() === "%" && tokens[i + 1] !== undefined && tokens[i + 1] !== ")")) {
            const op = take();
            operators++;
            const r = power();
            v = op === "*" ? v * r : op === "/" ? v / r : v % r;
        }
        return v;
    }
    function sum() {
        let v = product();
        while (peek() === "+" || peek() === "-") {
            const op = take();
            operators++;
            const r = product();
            v = op === "+" ? v + r : v - r;
        }
        return v;
    }
    const value = sum();
    if (i !== tokens.length)
        throw 0;
    return {value, operators};
}

// Returns {result, expression} or null when the query is not a calculation.
function evaluate(query) {
    let q = query.trim().toLowerCase().replace(/×/g, "*").replace(/÷/g, "/").replace(/−/g, "-");
    if (!q || q.length > 160)
        return null;
    // No lookbehind: QML's JavaScript engine does not support it, so the preceding character
    // is captured and put back ("2x2x2" -> "2*2*2", "1,5" -> "1.5").
    q = q.replace(/([\d)])\s*x\s*(?=[\d(])/g, "$1*").replace(/(\d),(?=\d)/g, "$1.");

    const conv = q.match(/^([-+]?\d+(?:\.\d+)?)\s*([a-z°]+)\s+(?:to|in|a|en)\s+([a-z°]+)$/);
    if (conv) {
        const n = parseFloat(conv[1]);
        const a = conv[2].replace("°", ""), b = conv[3].replace("°", "");
        let r = null;
        if (a === "c" && b === "f") r = n * 9 / 5 + 32;
        else if (a === "f" && b === "c") r = (n - 32) * 5 / 9;
        else if (a === "c" && b === "k") r = n + 273.15;
        else if (a === "k" && b === "c") r = n - 273.15;
        else if (UNITS[a] && UNITS[b] && UNITS[a][0] === UNITS[b][0]) r = n * UNITS[a][1] / UNITS[b][1];
        const f = r === null ? null : format(r);
        const label = ["c", "f", "k"].includes(b) ? (b === "k" ? "K" : "°" + b.toUpperCase()) : b;
        return f === null ? null : {result: f + " " + label, value: f + " " + label, expression: query.trim()};
    }

    // "15% of 80" -> 15% * 80
    q = q.replace(/(\d+(?:\.\d+)?)\s*%\s*(?:of|de)\s*/g, "$1% * ");
    if (!/\d/.test(q) || /^\d{4}-\d{1,2}-\d{1,2}/.test(q))
        return null; // no digits, or a date such as 2026-01-13
    const tokens = tokenize(q);
    if (!tokens || tokens.length > 60)
        return null;
    try {
        const parsed = parse(tokens);
        if (parsed.operators === 0)
            return null; // a bare number is not a calculation
        const f = format(parsed.value);
        return f === null ? null : {result: f, value: f, expression: query.trim()};
    } catch (e) {
        return null;
    }
}
