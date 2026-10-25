.pragma library
.import "Search.js" as Search
.import "Calc.js" as Calc
.import "Files.js" as Files
.import "Translate.js" as Translate
.import "Quick.js" as Quick
.import "Usage.js" as Usage

// Pure result builders. `ctx` is a snapshot of the in-memory indexes (apps, commands,
// clipboard, files, usage); nothing here touches processes or the filesystem.

function tag(rows, section) {
    return rows.map(r => Object.assign({}, r, {section}));
}

function appBoost(r) {
    return Math.min(Math.log(1 + (r.freq || 0)) * 25, 120);
}

// Deterministic order: frequency, then name, then key.
function byFrequency(a, b) {
    return (b.freq || 0) - (a.freq || 0) || (a.l < b.l ? -1 : a.l > b.l ? 1 : 0) || (a.key < b.key ? -1 : 1);
}

// All-time launches counted by the app database, before the launcher learned anything itself.
function appPrior(r) {
    return appBoost(r) * 0.5;
}

// Suggestions are frozen while the launcher is open: `snapshot` is the list taken on open.
// Entries are refreshed from live data when still present, but never reordered, added or
// dropped, so transient source updates cannot move what is on screen.
function keepOrder(snapshot, live) {
    const byKey = {};
    live.forEach(r => byKey[r.key] = r);
    return snapshot.map(r => byKey[r.key] ? Object.assign({}, byKey[r.key], {section: "Suggestions", pinned: r.pinned}) : r);
}

// Pins, then one ranking of what is opened most and most recently (at this time of day more than at
// others) together with long-time favourites from the app database. Files are capped so apps and
// commands stay in view; a fresh install gets a few starting points.
const SUGGESTED_FILES = 3;

function suggestions(ctx, now) {
    const out = [], seen = {};
    const add = (r, pinned) => {
        if (r && !seen[r.key]) {
            seen[r.key] = true;
            out.push(Object.assign({}, r, {section: "Suggestions", pinned: !!pinned}));
        }
    };
    ctx.pins.forEach(r => add(r, true));
    const when = now || Date.now();
    const usage = ctx.usage || {};
    const byKey = {}, score = {};
    ctx.commands.concat(ctx.settings || []).forEach(r => byKey[r.key] = r);
    ctx.apps.forEach(r => {
        byKey[r.key] = r;
        if (r.freq > 0)
            score[r.key] = 0.2 * Math.log2(1 + r.freq);
    });
    for (const k in usage) {
        const row = byKey[k] || (usage[k].row && usage[k].row.kind === "file" ? usage[k].row : null);
        if (row) {
            byKey[k] = row;
            score[k] = (score[k] || 0) + Usage.suggestionScore(usage[k], when);
        }
    }
    let files = 0;
    Object.keys(score).filter(k => score[k] > 0.02)
        .sort((a, b) => score[b] - score[a] || byFrequency(byKey[a], byKey[b]))
        .forEach(k => {
            if (out.length >= 9 || seen[k] || (byKey[k].kind === "file" && files++ >= SUGGESTED_FILES))
                return;
            add(byKey[k]);
        });
    if (out.length < 6) {
        const wanted = ["cmd:clipboard", "cmd:emoji", "cmd:wallpaper", "cmd:files", "cmd:settings"];
        ctx.commands.filter(c => wanted.includes(c.key)).forEach(c => add(c));
    }
    return out.slice(0, 9);
}

// Prefixes skip the search and act on the rest of the text. The first row is always what was typed;
// what follows is live (suggestions, history, alternatives), passed as `extra.live`, and only used
// while it still belongs to the text on screen. `extra` is {engine, live, now, random}: kept apart from
// the context so building it never copies the indexes.
const Sites = {
    "?": {id: "google", name: "Google", base: "https://www.google.com/search?q="},
    "!": {id: "youtube", name: "YouTube", base: "https://www.youtube.com/results?search_query="}
};

// The engine behind the plain "Search the web" row (Settings > Apps); "?" is always Google.
const Engines = {
    duckduckgo: {name: "DuckDuckGo", base: "https://duckduckgo.com/?q="},
    google: {name: "Google", base: "https://www.google.com/search?q=", brand: "google"},
    bing: {name: "Bing", base: "https://www.bing.com/search?q="},
    brave: {name: "Brave Search", base: "https://search.brave.com/search?q="},
    ecosia: {name: "Ecosia", base: "https://www.ecosia.org/search?q="}
};

function hero(key, props) {
    return Object.assign({kind: "hero", header: true, key: key, section: ""}, props);
}

function webRow(site, text, extra) {
    return Object.assign({kind: "web", key: "web", title: "Search " + site.name + " for “" + text + "”", subtitle: "Brave", icon: "travel_explore", brand: site.id, site: site.name, type: "Web", url: site.base + encodeURIComponent(text), section: ""}, extra);
}

function searchRows(site, rest, live) {
    if (!rest)
        return [hero("hero:" + site.id, {brand: site.id, icon: "travel_explore", title: "Search " + site.name, subtitle: "Opens in Brave. Start typing to see suggestions as you go."})];
    const rows = [webRow(site, rest)];
    const fresh = live.kind === site.id && live.query === rest ? live.items || [] : [];
    fresh.forEach(text => rows.push(webRow(site, text, {key: "suggest:" + text, title: text, subtitle: "Suggestion", icon: "search", brand: "", type: "", section: "Suggestions"})));
    return rows;
}

function commandRows(rest, live) {
    const fresh = live.kind === "run" && live.query === rest ? live.items || [] : [];
    const history = fresh.filter(c => c !== rest).map(c => ({kind: "run", key: "hist:" + c, title: c, subtitle: "Run it again", icon: "history", type: "History", command: c, section: rest ? "From your history" : "Recent commands"}));
    if (!rest)
        return history.length ? history : [hero("hero:run", {icon: "terminal", title: "Run in a terminal", subtitle: "Whatever follows > runs exactly as typed. Your recent commands will show up here."})];
    return [{kind: "run", key: "run", title: "Run “" + rest + "” in a terminal", subtitle: "Command", icon: "terminal", type: "Terminal", command: rest, section: ""}].concat(history);
}

function capitalise(text) {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

// The card shows the live result from Translator.qml; this row only carries what to translate.
function translateRows(rest, live) {
    const t = Translate.splitQuery(rest);
    if (!t.text)
        return [hero("hero:translate", {icon: "translate", title: "Translate", subtitle: "Type after ; to translate. Name a language first to choose it.", examples: [";en hola", ";fr gracias", ";ja good morning"]})];
    const rows = [{kind: "translate", key: "translate", title: t.text, subtitle: "", icon: "translate", type: "Translate", text: t.text, target: t.target, section: ""}];
    if (live.state === "done" && live.answered === t.text) {
        (live.variants || []).forEach(v => rows.push({kind: "variant", key: "variant:" + v, title: v, subtitle: "Another way to say it", icon: "translate", type: "Copy", value: v, section: "Other ways to say it"}));
        const shown = (live.variants || []).map(v => v.toLowerCase());
        (live.meanings || []).forEach(m => m.words.filter(w => !shown.includes(w.toLowerCase())).forEach(w => rows.push({kind: "variant", key: "meaning:" + m.pos + ":" + w, title: w, subtitle: "Meaning", icon: "menu_book", type: "Copy", value: w, section: capitalise(m.pos)})));
    }
    return rows;
}

function root(query, ctx, extra) {
    const q = query.trim();
    const more = extra || {};
    if (!q)
        return suggestions(ctx, more.now);
    const live = more.live || {};
    switch (q[0]) {
    case "?":
    case "!":
        return searchRows(Sites[q[0]], q.slice(1).trim(), live.suggest || {});
    case ">":
        return commandRows(q.slice(1).trim(), live.suggest || {});
    case ";":
        return translateRows(q.slice(1), live.translation || {});
    }
    if (/^kill(\s|$)/i.test(q))
        return Quick.killRows(live.procs && live.procs.query === q.slice(4).trim() ? live.procs.items : [], q.length > 4);
    const ts = Search.terms(q);
    let rows = Quick.rows(q, more);
    const calc = Calc.evaluate(q);
    if (calc)
        rows.push({kind: "calc", key: "calc", title: calc.result, subtitle: calc.expression, icon: "calculate", type: "Calculator", value: calc.value, expression: calc.expression, section: ""});
    const groups = [];
    const group = (name, hits) => {
        if (hits.length)
            groups.push({name, rows: hits.map(h => h.item), top: hits[0].score});
    };
    const learn = Usage.booster(ctx.usage || {}, ctx.picks || [], q, more.now || Date.now());
    group("Applications", Search.rankScored(ts, ctx.apps, ctx.maxApps, r => appPrior(r) + learn(r)));
    group("Commands", Search.rankScored(ts, ctx.commands, 4, learn));
    // Settings are mostly found by keyword ("pantallas", "wifi"), which scores like a weak match: lift
    // those above a page of file names, without letting a page beat an app named like it.
    const keyword = r => ts.some(t => Search.termScore(t, r.l, true) > 0) ? 0 : 150;
    group("Settings", Search.rankScored(ts, ctx.settings || [], 3, r => keyword(r) + learn(r)));
    if (ctx.files.length) {
        // The file search ranks by name; files opened before move up within it (stable otherwise).
        const files = ctx.files.map((r, i) => ({r, i, b: learn(r)})).sort((x, y) => y.b - x.b || x.i - y.i).slice(0, 8);
        groups.push({name: "Files", rows: files.map(f => f.r), top: 350 + files[0].b});
    }
    group("Clipboard", Search.rankScored(ts, ctx.clips, 3));
    groups.sort((x, y) => y.top - x.top); // stable: ties keep the order above
    for (const g of groups)
        rows = rows.concat(tag(g.rows, g.name));
    const engine = Engines[more.engine] || Engines.duckduckgo;
    rows.push({kind: "web", key: "web", title: "Search the web for “" + q + "”", subtitle: engine.name, icon: "travel_explore", brand: engine.brand || "", site: "the Web", type: "Web", url: engine.base + encodeURIComponent(q), section: "Fallbacks"});
    rows.push({kind: "run", key: "run", title: "Run “" + q + "” in a terminal", subtitle: "Executes exactly what you typed", icon: "terminal", type: "Terminal", command: q, section: "Fallbacks"});
    return rows;
}

function dayLabel(stamp) {
    const now = new Date(), d = new Date(stamp * 1000);
    const day = x => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((day(now) - day(d)) / 86400000);
    return diff <= 0 ? "Today" : diff === 1 ? "Yesterday" : "Earlier";
}

function filtered(query, list, limit) {
    const q = query.trim();
    return q ? Search.rank(Search.terms(q), list, limit) : list.slice(0, limit);
}

// An image whose recognized text matched the query shows the matching line instead of its date.
function ocrSnippet(row, query) {
    if (row.clip_kind !== "image" || !row.ocr || !query.trim())
        return row;
    const lines = row.ocr.split("\n").map(x => x.trim()).filter(Boolean);
    const ts = Search.terms(query);
    const hit = lines.find(x => ts.some(t => x.toLowerCase().includes(t)));
    return hit ? Object.assign({}, row, {subtitle: "“" + hit.slice(0, 90) + "”  ·  Alt K › Copy Text"}) : row;
}

function view(id, query, ctx, target, filter) {
    switch (id) {
    case "clipboard":
        return filtered(query, ctx.clips.filter(r => !filter || filter === "all" || r.clip_kind === filter), 150).map(r => Object.assign({}, ocrSnippet(r, query), {section: query.trim() ? "Matches" : dayLabel(r.stamp)}));
    case "files":
        const keep = r => !filter || filter === "all" || (filter === "image" ? !r.isDir && Files.isImage(r.path) : r.isDir);
        if (query.trim())
            return tag(ctx.files.filter(keep), "Results");
        return tag(filter && filter !== "all" ? [] : ctx.places, "Places").concat(tag(ctx.recentFiles.filter(keep).slice(0, 40), "Recent Files"));
    case "browse": {
        const keep2 = r => !filter || filter === "all" || (filter === "image" ? !r.isDir && Files.isImage(r.path) : r.isDir);
        // Typing searches this folder and every subfolder; empty query lists the folder itself.
        if (query.trim())
            return tag(ctx.files.filter(keep2), "Results");
        const rows = ctx.browse.filter(keep2);
        return tag(rows.filter(r => r.isDir), "Folders").concat(tag(rows.filter(r => !r.isDir), "Files"));
    }
    case "apps": {
        const learn = Usage.booster(ctx.usage || {}, ctx.picks || [], query, Date.now());
        const sorted = query.trim() ? Search.rank(Search.terms(query), ctx.apps, 200, r => appBoost(r) + learn(r)) : ctx.apps.slice().sort((a, b) => a.l < b.l ? -1 : 1);
        return tag(sorted, "Applications");
    }
    case "openwith":
        return tag(Search.rank(Search.terms(query), ctx.apps, 200, appBoost).map(r => Object.assign({}, r, {kind: "openwith", target})), "Open With");
    case "calc-history":
        return tag(filtered(query, ctx.calcHistory, 100), "History");
    }
    return [];
}

function emptyText(id, query) {
    if (query.trim() && id === "root")
        return "No results for “" + query.trim() + "”";
    return {
        clipboard: "Your next copy starts the history.\nText, images, colours and links.",
        files: query.trim() ? "No files match." : "No recent files.",
        browse: query.trim() ? "Nothing in this folder matches." : "This folder is empty.",
        "calc-history": "Copy a calculator result and it shows up here.",
        apps: "No applications match."
    }[id] || "Nothing here.";
}
