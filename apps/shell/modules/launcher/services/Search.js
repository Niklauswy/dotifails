.pragma library

// Fuzzy scoring over in-memory data. Each target is {l: lowercased primary text, a: lowercased auxiliary text}.
// Returns 0 for no match; higher is better. Cheap enough to run per keystroke on thousands of entries.

function termScore(t, s, fuzzy) {
    if (!s)
        return 0;
    if (s === t)
        return 1000;
    if (s.startsWith(t))
        return 800 - Math.min(s.length - t.length, 100) * 0.5;
    const word = s.indexOf(" " + t);
    if (word >= 0)
        return 600 - Math.min(word, 100) * 0.5;
    const at = s.indexOf(t);
    if (at >= 0)
        return 400 - Math.min(at, 100) * 0.5;
    if (!fuzzy || t.length < 2 || s.length > 48)
        return 0;
    // Subsequence: every char of t in order; reward word starts and tight runs.
    let si = 0, gaps = 0, bonus = 0, prev = -2;
    for (let ti = 0; ti < t.length; ti++) {
        const c = t.charCodeAt(ti);
        let found = -1;
        for (; si < s.length; si++) {
            if (s.charCodeAt(si) === c) { found = si++; break; }
        }
        if (found < 0)
            return 0;
        if (found === prev + 1) bonus += 6;
        else gaps += found - prev - 1;
        if (found === 0 || s.charCodeAt(found - 1) === 32 || s.charCodeAt(found - 1) === 45) bonus += 10;
        prev = found;
    }
    return Math.max(10, 150 + bonus - Math.min(gaps, 100));
}

function terms(query) {
    return query.toLowerCase().split(/\s+/).filter(Boolean);
}

function score(ts, target) {
    let total = 0;
    for (let i = 0; i < ts.length; i++) {
        const p = termScore(ts[i], target.l, true);
        const a = p ? 0 : termScore(ts[i], target.a, false) * 0.35;
        if (!p && !a)
            return 0;
        total += p || a;
    }
    return total;
}

// Best `limit` items by score (+ boost(item)), stable for ties.
function rank(ts, items, limit, boost) {
    return rankScored(ts, items, limit, boost).map(h => h.item);
}

function rankScored(ts, items, limit, boost) {
    const hits = [];
    for (let i = 0; i < items.length; i++) {
        const s = score(ts, items[i]);
        if (s > 0)
            hits.push({item: items[i], score: s + (boost ? boost(items[i]) : 0), order: i});
    }
    hits.sort((x, y) => y.score - x.score || x.order - y.order);
    return hits.slice(0, limit);
}
