// Recursive file search over the in-memory tree index (`d<path>` / `f<path>` lines relative to HOME).
// Every query token must match (AND). A token is scored against the entry name first (exact, prefix,
// word start, substring, subsequence) and then against the folders above it, so "docs inv pdf" finds
// Documents/Invoices/2024/march.pdf. Appending characters can only shrink the match set, so a query that
// extends the previous one is evaluated over the previous candidates only.

const ASCII = /^[\x00-\x7f]*$/;

export function fold(text) {
    const s = text.toLowerCase();
    return ASCII.test(s) ? s : s.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export function parse(text) {
    const lines = text ? text.split("\n") : [];
    const n = lines.length;
    const index = {p: new Array(n), l: new Array(n), a: new Array(n), d: new Array(n), size: 0};
    let k = 0;
    for (let i = 0; i < n; i++) {
        const line = lines[i];
        if (line.length < 2)
            continue;
        const path = line.slice(1);
        index.p[k] = path;
        index.d[k] = line[0] === "d";
        index.a[k] = fold(path);
        index.l[k] = index.a[k].slice(index.a[k].lastIndexOf("/") + 1);
        k++;
    }
    index.size = k;
    return index;
}

export function terms(query) {
    return fold(query).split(/\s+/).filter(Boolean);
}

// Subsequence match inside a name; rewards runs and word starts. 0 when t is not a subsequence.
export function fuzzy(t, s) {
    let si = 0, prev = -2, score = 120;
    for (let ti = 0; ti < t.length; ti++) {
        const at = s.indexOf(t[ti], si);
        if (at < 0)
            return 0;
        if (at === prev + 1)
            score += 8;
        else
            score -= Math.min(at - prev - 1, 12);
        if (at === 0 || " ._-".indexOf(s[at - 1]) >= 0)
            score += 10;
        prev = at;
        si = at + 1;
    }
    return Math.max(score, 20);
}

// Score of one token for entry i; `off` is where the searched part of the path starts.
export function tokenScore(t, name, path, off) {
    if (name === t)
        return 1000;
    if (name.startsWith(t))
        return 800 - Math.min(name.length - t.length, 100) * 0.5;
    const at = name.indexOf(t);
    if (at >= 0) {
        const boundary = " ._-".indexOf(name[at - 1]) >= 0;
        return (boundary ? 650 : 420) - Math.min(at, 100) * 0.5;
    }
    if (t.length >= 2 && name.length <= 64) {
        const f = fuzzy(t, name);
        if (f)
            return f;
    }
    const inPath = path.indexOf(t, off);
    if (inPath >= 0 && inPath < path.length - name.length)
        return 160 - Math.min(inPath - off, 100) * 0.3;
    return 0;
}

// Returns {rows: [{i, s}], candidates, q, scope} with at most `limit` rows ordered by score.
// `prev` is the result of the previous call for the same index; pass null to start fresh.
export function search(index, query, scope, limit, prev) {
    const q = fold(query).trim();
    const ts = q.split(/\s+/).filter(Boolean);
    if (!ts.length || !index || !index.size)
        return {rows: [], candidates: null, q: "", scope};
    const base = scope ? fold(scope) + "/" : "";
    const off = base.length;
    const reuse = prev && prev.candidates && prev.index === index && prev.scope === scope && prev.q && q.startsWith(prev.q);
    const source = reuse ? prev.candidates : null;
    const count = source ? source.length : index.size;
    // Hidden entries are indexed but rank below visible ones unless the query itself asks for a dot-name.
    const wantsHidden = ts.some(t => t[0] === ".");
    const candidates = [];
    const hits = [];
    for (let j = 0; j < count; j++) {
        const i = source ? source[j] : j;
        const path = index.a[i];
        if (off && !path.startsWith(base))
            continue;
        const name = index.l[i];
        let total = 0;
        for (let k = 0; k < ts.length; k++) {
            const s = tokenScore(ts[k], name, path, off);
            if (!s) {
                total = 0;
                break;
            }
            total += s;
        }
        if (!total)
            continue;
        candidates.push(i);
        // Shorter names/paths and shallower entries first; folders slightly ahead on equal footing.
        const hidden = !wantsHidden && (path[0] === "." || path.indexOf("/.") >= 0);
        hits.push({i, s: total - (path.length - off) * 0.15 + (index.d[i] ? 12 : 0) - (hidden ? 120 : 0)});
    }
    hits.sort((x, y) => y.s - x.s || x.i - y.i);
    return {rows: hits.slice(0, limit), candidates, q, scope, index};
}
