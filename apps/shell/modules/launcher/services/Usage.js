.pragma library

// Learned ranking. For every entry opened from the launcher it keeps when it was opened (the last few
// times, so old habits fade), at which hours, and what had been typed when it was picked. Pure functions
// over plain data; LauncherIndex persists the two maps in launcher.json.
//
//   usage: {key: {n, t: [newest first, ms], h: [24 counts], row?}}   row: snapshot for files and views
//   picks: [{q, k, n, t}]                                            q: normalised query, k: key

const DAY = 86400000;
const HALF_LIFE = 5 * DAY;
const PICK_HALF_LIFE = 30 * DAY;
const HISTORY = 12;
const MAX_ENTRIES = 300;
const MAX_PICKS = 400;

function normal(query) {
    return query.trim().toLowerCase().replace(/\s+/g, " ");
}

// Sum of the recent uses, each worth 1 when it just happened and half as much every HALF_LIFE.
// Uses that fell out of the history still count a little, so a long habit outweighs a burst.
function frecency(entry, now) {
    if (!entry)
        return 0;
    let total = 0;
    for (let i = 0; i < entry.t.length; i++)
        total += Math.pow(2, -Math.max(0, now - entry.t[i]) / HALF_LIFE);
    return total + 0.1 * Math.log2(1 + Math.max(0, entry.n - entry.t.length));
}

// 0..1: how much of this entry's use happens around `hour` (neighbouring hours count half).
function hourAffinity(entry, hour) {
    if (!entry || !entry.h)
        return 0;
    let total = 0;
    for (let i = 0; i < 24; i++)
        total += entry.h[i];
    if (total < 3)
        return 0;
    return Math.min(1, (entry.h[hour] + 0.5 * (entry.h[(hour + 23) % 24] + entry.h[(hour + 1) % 24])) / total);
}

// -> {usage, picks}: new objects with one more use of `key`. `row` is kept for entries that cannot be
// looked up again by key (files, folders); `query` is what was typed, "" from the suggestions.
function record(usage, picks, key, query, now, row) {
    const old = usage[key];
    const entry = {
        n: (old ? old.n : 0) + 1,
        t: [now].concat(old ? old.t : []).slice(0, HISTORY),
        h: old && old.h ? old.h.slice() : new Array(24).fill(0)
    };
    entry.h[new Date(now).getHours()]++;
    if (row)
        entry.row = row;
    else if (old && old.row)
        entry.row = old.row;
    let nextUsage = Object.assign({}, usage);
    nextUsage[key] = entry;
    const keys = Object.keys(nextUsage);
    if (keys.length > MAX_ENTRIES) {
        keys.sort((a, b) => frecency(nextUsage[b], now) - frecency(nextUsage[a], now));
        const kept = {};
        keys.slice(0, MAX_ENTRIES).forEach(k => kept[k] = nextUsage[k]);
        nextUsage = kept;
    }
    let nextPicks = picks;
    const q = normal(query || "");
    if (q) {
        let found = false;
        nextPicks = picks.map(p => {
            if (p.q !== q || p.k !== key)
                return p;
            found = true;
            return {q, k: key, n: p.n + 1, t: now};
        });
        if (!found)
            nextPicks.push({q, k: key, n: 1, t: now});
        if (nextPicks.length > MAX_PICKS)
            nextPicks = nextPicks.slice().sort((a, b) => b.t - a.t).slice(0, MAX_PICKS);
    }
    return {usage: nextUsage, picks: nextPicks};
}

// -> {key: boost} for what was picked after typing something like `query`: the same text counts fully,
// a longer or shorter version of it in proportion to how much of it overlaps.
function queryBoosts(picks, query, now) {
    const q = normal(query);
    const out = {};
    if (!q)
        return out;
    for (let i = 0; i < picks.length; i++) {
        const p = picks[i];
        let w = 0;
        if (p.q === q)
            w = 1;
        else if (p.q.startsWith(q))
            w = 0.35 + 0.5 * q.length / p.q.length;
        else if (q.startsWith(p.q))
            w = 0.6 * p.q.length / q.length;
        if (!w)
            continue;
        const decay = Math.pow(2, -Math.max(0, now - p.t) / PICK_HALF_LIFE);
        out[p.k] = (out[p.k] || 0) + 130 * w * decay * Math.log2(1 + p.n);
    }
    for (const k in out)
        out[k] = Math.min(out[k], 450);
    return out;
}

// Extra score for a search hit: its own habit (frecency) plus what this query has led to before.
// Only added to entries whose text already matched, so learning reorders but never invents results.
function booster(usage, picks, query, now) {
    const learned = queryBoosts(picks, query, now);
    return item => Math.min(220, 70 * Math.log2(1 + frecency(usage[item.key], now))) + (learned[item.key] || 0);
}

// Weight of an entry in the empty launcher: frecency, more for what is usually opened at this hour.
function suggestionScore(entry, now) {
    return frecency(entry, now) * (0.7 + 0.6 * hourAffinity(entry, new Date(now).getHours()));
}

// Ranked keys for the empty launcher.
function suggested(usage, now) {
    return Object.keys(usage)
        .map(k => ({k, s: suggestionScore(usage[k], now)}))
        .filter(x => x.s > 0.02)
        .sort((a, b) => b.s - a.s || (a.k < b.k ? -1 : 1))
        .map(x => x.k);
}

// One-time import of the old `recent` list (newest first) as single uses a day apart, so it seeds the
// suggestions without crowding out what gets opened from now on.
function fromRecent(recent, now) {
    const usage = {};
    recent.forEach((r, i) => {
        const t = now - (i + 1) * DAY;
        const h = new Array(24).fill(0);
        h[new Date(t).getHours()]++;
        usage[r.key] = {n: 1, t: [t], h, row: r.row};
    });
    return usage;
}
